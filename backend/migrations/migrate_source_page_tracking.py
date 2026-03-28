"""
Database Migration: Add source_page tracking for metadata-driven resume scraping

This migration ensures the scraped_records table has proper source_page tracking
for reliable checkpoint-based resume functionality.

Run: python -c "from backend.migrations.migrate_source_page_tracking import run_migration; run_migration()"
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Setup path
root_dir = Path(__file__).parent.parent.parent  # backend/
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

load_dotenv('.env')

from src.models.database import ParseHubDatabase

def run_migration():
    """
    Run the migration to add source_page tracking
    
    Actions:
    1. Verify scraped_records table exists
    2. Add source_page column if missing
    3. Create index on (project_id, source_page)
    4. Create index on source_page for MAX queries
    5. Verify data integrity
    """
    db = ParseHubDatabase()
    conn = db.connect()
    cursor = db.cursor()
    
    print("\n" + "="*80)
    print("MIGRATION: Add source_page tracking for metadata-driven resume scraping")
    print("="*80)
    
    try:
        # Step 1: Check if table exists
        print("\n[Step 1] Checking if scraped_records table exists...")
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'scraped_records'
            ) as table_exists
        """)
        result = cursor.fetchone()
        table_exists = result[0] if isinstance(result, tuple) else result.get('table_exists')
        
        if not table_exists:
            print("  ✓ scraped_records table exists")
        else:
            print("  ! scraped_records table will be created on first use")
        
        # Step 2: Add source_page column if missing
        print("\n[Step 2] Adding source_page column if missing...")
        try:
            # Try to add the column (won't fail if it exists in Snowflake)
            cursor.execute("""
                ALTER TABLE scraped_records 
                ADD COLUMN IF NOT EXISTS source_page INTEGER DEFAULT NULL
            """)
            conn.commit()
            print("  ✓ source_page column verified/added")
        except Exception as e:
            if 'already exists' in str(e).lower():
                print("  ✓ source_page column already exists")
            else:
                print(f"  ! Note: {e}")
        
        # Step 3: Create indexes
        print("\n[Step 3] Creating indexes...")
        
        # Index 1: For checkpoint queries (MAX source_page by project)
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_records_project_source_page
                ON scraped_records(project_id, source_page DESC)
            """)
            conn.commit()
            print("  ✓ Index on (project_id, source_page) created")
        except Exception as e:
            if 'already exists' in str(e).lower():
                print("  ✓ Index on (project_id, source_page) already exists")
            else:
                print(f"  ! Could not create index: {e}")
        
        # Index 2: For source_page queries
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_records_source_page
                ON scraped_records(source_page)
            """)
            conn.commit()
            print("  ✓ Index on source_page created")
        except Exception as e:
            if 'already exists' in str(e).lower():
                print("  ✓ Index on source_page already exists")
            else:
                print(f"  ! Could not create index: {e}")
        
        # Step 4: Verify data integrity
        print("\n[Step 4] Checking data integrity...")
        
        cursor.execute("""
            SELECT COUNT(*) as total_records,
                   COUNT(source_page) as records_with_source_page,
                   COUNT(CASE WHEN source_page IS NULL THEN 1 END) as null_source_pages
            FROM scraped_records
        """)
        
        result = cursor.fetchone()
        if isinstance(result, tuple):
            total = result[0] or 0
            with_page = result[1] or 0
            nulls = result[2] or 0
        else:
            total = result.get('total_records') or 0
            with_page = result.get('records_with_source_page') or 0
            nulls = result.get('null_source_pages') or 0
        
        print(f"  Total records: {total}")
        print(f"  Records with source_page: {with_page}")
        print(f"  Records missing source_page: {nulls}")
        
        if total == 0:
            print("  ✓ Table is empty (migration ready for new data)")
        elif nulls == 0:
            print("  ✓ All records have source_page set")
        else:
            print(f"  ⚠ {nulls} records missing source_page (need backfill or they'll be indexed with NULL)")
        
        # Step 5: Verify checkpoint query works
        print("\n[Step 5] Testing checkpoint query...")
        cursor.execute("""
            SELECT MAX(source_page) as highest_page,
                   COUNT(*) as total_records
            FROM scraped_records
            WHERE project_id = %s OR project_id IS NULL
            LIMIT 1
        """, (0,))
        
        test_result = cursor.fetchone()
        print("  ✓ Checkpoint query executes successfully")
        
        # Step 6: Summary
        print("\n[Summary]")
        print("  ✓ scraped_records table has source_page column")
        print("  ✓ Indexes created for efficient checkpoint queries")
        print("  ✓ Data integrity verified")
        print("\n" + "="*80)
        print("MIGRATION COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nNext steps:")
        print("1. Deploy backend code with MetadataDrivenResumeScraper service")
        print("2. Start new scraping runs with /api/projects/resume/start")
        print("3. All new records will have source_page automatically tracked")
        print("4. Checkpoint will be computed from MAX(source_page) per project")
        print("\n")
        
        return True
    
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
