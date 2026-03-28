"""
DATABASE MIGRATION FOR CHUNK-BASED PAGINATION
Supports Snowflake schema updates for batch scraping with proper checkpoints

Changes:
1. Add is_batch_run flag to runs table
2. Ensure metadata table has current_page_scraped tracking
3. Ensure product_data table supports source_page column
4. Migration of existing runs data (if needed)
"""

# Migration SQL for Snowflake

MIGRATION_SQL = """
-- ===== RUNS TABLE UPDATES =====

-- Add is_batch_run flag to track batch-based runs
-- (tracks 10-page batch processing)
ALTER TABLE IF EXISTS runs
ADD COLUMN IF NOT EXISTS is_batch_run BOOLEAN DEFAULT FALSE;

-- Add batch identifier to link batch components
ALTER TABLE IF EXISTS runs
ADD COLUMN IF NOT EXISTS batch_id VARCHAR(255);

-- Index for batch queries
CREATE INDEX IF NOT EXISTS idx_runs_is_batch_run ON runs(is_batch_run);
CREATE INDEX IF NOT EXISTS idx_runs_batch_id ON runs(batch_id);

-- ===== METADATA TABLE (already has current_page_scraped) =====

-- Ensure start_url exists in metadata for batch checkpoint reading
ALTER TABLE IF EXISTS metadata
ADD COLUMN IF NOT EXISTS start_url VARCHAR(2048);

-- Ensure total_pages is tracked
ALTER TABLE IF EXISTS metadata
ADD COLUMN IF NOT EXISTS total_pages INTEGER DEFAULT 0;

-- Tracking for current progress
ALTER TABLE IF EXISTS metadata
ADD COLUMN IF NOT EXISTS current_page_scraped INTEGER DEFAULT 0;

-- Index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_metadata_current_page ON metadata(current_page_scraped);

-- ===== PRODUCT_DATA TABLE UPDATES =====

-- Add source_page for batch deduplication
ALTER TABLE IF EXISTS product_data
ADD COLUMN IF NOT EXISTS source_page INTEGER;

-- Add batch tracking
ALTER TABLE IF EXISTS product_data
ADD COLUMN IF NOT EXISTS batch_id VARCHAR(255);

-- Indexes for deduplication and batch queries
CREATE INDEX IF NOT EXISTS idx_product_data_source_page ON product_data(source_page);
CREATE INDEX IF NOT EXISTS idx_product_data_batch_id ON product_data(batch_id);

-- ===== BATCH CHECKPOINT TABLE (NEW) =====

-- Create dedicated checkpoint table for batch progress tracking
CREATE TABLE IF NOT EXISTS batch_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    project_token VARCHAR(255) NOT NULL,
    checkpoint_type VARCHAR(50) NOT NULL,  -- 'batch_start', 'batch_complete', 'cycle_complete'
    last_completed_page INTEGER,
    batch_start_page INTEGER,
    batch_end_page INTEGER,
    total_items_from_batch INTEGER DEFAULT 0,
    batch_status VARCHAR(50) DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'failed'
    run_token VARCHAR(255),
    checkpoint_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient checkpoint queries
CREATE INDEX IF NOT EXISTS idx_batch_checkpoints_project_id ON batch_checkpoints(project_id);
CREATE INDEX IF NOT EXISTS idx_batch_checkpoints_project_token ON batch_checkpoints(project_token);
CREATE INDEX IF NOT EXISTS idx_batch_checkpoints_timestamp ON batch_checkpoints(checkpoint_timestamp);
CREATE INDEX IF NOT EXISTS idx_batch_checkpoints_run_token ON batch_checkpoints(run_token);
"""

def run_migration(database):
    """
    Run migration on Snowflake database
    
    Args:
        database: ParseHubDatabase instance
    
    Returns:
        {'success': bool, 'messages': list, 'errors': list}
    """
    import logging
    logger = logging.getLogger(__name__)
    
    messages = []
    errors = []
    
    try:
        conn = database.connect()
        cursor = database.cursor()
        
        # Split migrations into individual statements
        statements = [s.strip() for s in MIGRATION_SQL.split(';') if s.strip()]
        
        for statement in statements:
            try:
                logger.info(f"[MIGRATION] Executing: {statement[:60]}...")
                cursor.execute(statement)
                messages.append(f"✓ {statement[:50]}...")
                logger.info(f"[MIGRATION] ✓")
            except Exception as e:
                if "already exists" in str(e) or "duplicate" in str(e).lower():
                    messages.append(f"⊘ {statement[:50]}... (already exists)")
                else:
                    error_msg = f"✗ {statement[:50]}... - {str(e)}"
                    errors.append(error_msg)
                    logger.warning(f"[MIGRATION] {error_msg}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"[MIGRATION] Complete: {len(messages)} succeeded, {len(errors)} errors")
        
        return {
            'success': len(errors) == 0,
            'messages': messages,
            'errors': errors
        }
    
    except Exception as e:
        logger.error(f"[MIGRATION] Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'messages': messages,
            'errors': [str(e)] + errors
        }


# Helper functions for checkpoint management

def get_latest_checkpoint(database, project_id: int) -> dict:
    """Get latest batch checkpoint for a project"""
    try:
        conn = database.connect()
        cursor = database.cursor()
        
        cursor.execute('''
            SELECT id, last_completed_page, batch_status, checkpoint_timestamp
            FROM batch_checkpoints
            WHERE project_id = %s
            ORDER BY checkpoint_timestamp DESC
            LIMIT 1
        ''', (project_id,))
        
        checkpoint = cursor.fetchone()
        conn.close()
        
        if checkpoint:
            return {
                'id': checkpoint.get('id') if isinstance(checkpoint, dict) else checkpoint[0],
                'last_completed_page': checkpoint.get('last_completed_page') if isinstance(checkpoint, dict) else checkpoint[1],
                'status': checkpoint.get('batch_status') if isinstance(checkpoint, dict) else checkpoint[2],
                'timestamp': checkpoint.get('checkpoint_timestamp') if isinstance(checkpoint, dict) else checkpoint[3]
            }
        else:
            return None
    
    except Exception as e:
        import logging
        logging.error(f"[CHECKPOINT] Error reading checkpoint: {e}")
        return None


def record_batch_checkpoint(database, project_id: int, project_token: str,
                           batch_start_page: int, batch_end_page: int,
                           last_completed_page: int, items_count: int = 0,
                           run_token: str = None, status: str = 'completed') -> bool:
    """Record a batch checkpoint"""
    try:
        conn = database.connect()
        cursor = database.cursor()
        
        from datetime import datetime
        
        cursor.execute('''
            INSERT INTO batch_checkpoints
            (project_id, project_token, checkpoint_type, batch_start_page, batch_end_page,
             last_completed_page, total_items_from_batch, batch_status, run_token)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (project_id, project_token, 'batch_complete', batch_start_page, batch_end_page,
              last_completed_page, items_count, status, run_token))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        import logging
        logging.error(f"[CHECKPOINT] Error recording checkpoint: {e}")
        return False
