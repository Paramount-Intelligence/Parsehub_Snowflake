-- Snowflake Database Schema Initialization
-- Snowflake-compatible DDL for all tables

-- Database and schema are created by Snowflake admin setup
-- This script creates tables with Snowflake-native syntax

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(1000) NOT NULL,
    owner_email VARCHAR(255),
    main_site VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Project Metadata Linking table
CREATE TABLE IF NOT EXISTS project_metadata (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    metadata_id INTEGER NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Metadata table - project metadata sourced from Excel imports
CREATE TABLE IF NOT EXISTS metadata (
    id INTEGER PRIMARY KEY,
    personal_project_id VARCHAR(255) UNIQUE NOT NULL,
    project_id INTEGER,
    project_token VARCHAR(255) UNIQUE,
    project_name VARCHAR(1000) NOT NULL,
    last_run_date TIMESTAMP,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    region VARCHAR(500),
    country VARCHAR(500),
    brand VARCHAR(500),
    website_url VARCHAR(1000),
    total_pages INTEGER,
    total_products INTEGER,
    current_page_scraped INTEGER DEFAULT 0,
    current_product_scraped INTEGER DEFAULT 0,
    last_known_url VARCHAR(1000),
    import_batch_id INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (project_token) REFERENCES projects(token)
);

-- Create indexes for metadata filtering and sorting
CREATE INDEX IF NOT EXISTS idx_metadata_region ON metadata (region);
CREATE INDEX IF NOT EXISTS idx_metadata_country ON metadata (country);
CREATE INDEX IF NOT EXISTS idx_metadata_brand ON metadata (brand);
CREATE INDEX IF NOT EXISTS idx_metadata_updated_date ON metadata (updated_date);
CREATE INDEX IF NOT EXISTS idx_metadata_status ON metadata (status);

-- Scheduled Runs table
CREATE TABLE IF NOT EXISTS scheduled_runs (
    id INTEGER PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    project_token VARCHAR(255) NOT NULL,
    schedule_type VARCHAR(50),
    scheduled_time TIMESTAMP,
    frequency VARCHAR(50),
    day_of_week VARCHAR(50),
    pages INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (project_token) REFERENCES projects(token)
);

-- Runs table for tracking project execution history
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    project_token VARCHAR(255) NOT NULL,
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    pages_scraped INTEGER,
    execution_time_seconds INTEGER,
    status VARCHAR(50),
    error_message TEXT,
    is_continuation BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (project_token) REFERENCES projects(token)
);

-- Scraped Data table
CREATE TABLE IF NOT EXISTS scraped_data (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    project_token VARCHAR(255) NOT NULL,
    data_url VARCHAR(1000),
    row_json TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (project_token) REFERENCES projects(token)
);

-- Scraped Records table - used by metadata-driven resume scraper
CREATE TABLE IF NOT EXISTS scraped_records (
    id INTEGER IDENTITY(1,1) PRIMARY KEY,
    session_id INTEGER,
    project_id INTEGER NOT NULL,
    run_token VARCHAR(255) NOT NULL,
    page_number INTEGER,
    source_page INTEGER DEFAULT 0,
    data_hash VARCHAR(64),
    data_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (session_id) REFERENCES monitoring_sessions(id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(run_token, page_number, data_hash)
);

-- Metrics table for tracking analytics
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY,
    project_token VARCHAR(255) NOT NULL,
    metric_type VARCHAR(100),
    metric_value FLOAT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (project_token) REFERENCES projects(token)
);

-- Import batches for tracking Excel file imports
CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY,
    file_name VARCHAR(500),
    file_path VARCHAR(1000),
    row_count INTEGER,
    status VARCHAR(50),
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Grant read-only access on tables
GRANT SELECT ON TABLE projects TO ROLE PUBLIC;
GRANT SELECT ON TABLE metadata TO ROLE PUBLIC;
GRANT SELECT ON TABLE scheduled_runs TO ROLE PUBLIC;
GRANT SELECT ON TABLE runs TO ROLE PUBLIC;
GRANT SELECT ON TABLE scraped_data TO ROLE PUBLIC;
GRANT SELECT ON TABLE metrics TO ROLE PUBLIC;
GRANT SELECT ON TABLE import_batches TO ROLE PUBLIC;
