"""Fix Snowflake scraped_records table schema"""
import sys
import os

os.chdir('d:/Parsehub-Snowflake/Parsehub_Snowflake/backend')
sys.path.insert(0, 'd:/Parsehub-Snowflake/Parsehub_Snowflake/backend')

from dotenv import load_dotenv
load_dotenv()

from src.models.database import ParseHubDatabase

db = ParseHubDatabase()
conn = db.connect()
cursor = db.cursor()

print("=" * 60)
print("FIXING SNOWFLAKE SCHEMA")
print("=" * 60)

# Step 1: Check current schema
print("\n1. Checking current schema...")
cursor.execute('''
    SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'SCRAPED_RECORDS'
    ORDER BY ORDINAL_POSITION
''', (db.sf_schema,))

current_columns = cursor.fetchall()
for col in current_columns:
    col_name = col.get('COLUMN_NAME') or col.get('column_name')
    nullable = col.get('IS_NULLABLE') or col.get('is_nullable')
    data_type = col.get('DATA_TYPE') or col.get('data_type')
    print(f"  - {col_name} ({data_type}) Nullable: {nullable}")

# Step 2: Check if fixes are needed
session_id_col = next((c for c in current_columns
    if (c.get('COLUMN_NAME') or c.get('column_name')) == 'SESSION_ID'), None)

if session_id_col:
    is_nullable = session_id_col.get('IS_NULLABLE') or session_id_col.get('is_nullable')
    if is_nullable == 'NO':
        print("\n2. SESSION_ID is NOT nullable - needs to be fixed!")

        # In Snowflake, we need to recreate the table to change nullability
        print("\n3. Creating new table with correct schema...")

        # Get current data
        cursor.execute('SELECT * FROM scraped_records LIMIT 1')
        has_data = cursor.fetchone() is not None

        if has_data:
            print("   WARNING: Table has data. Will preserve it.")
            # Save existing data
            cursor.execute('SELECT * FROM scraped_records')
            existing_data = cursor.fetchall()
            print(f"   Found {len(existing_data)} records to preserve")

        # Drop and recreate table
        cursor.execute('DROP TABLE scraped_records')
        print("   Dropped old table")

        # Create new table with correct schema
        cursor.execute('''
            CREATE TABLE scraped_records (
                id INTEGER IDENTITY(1,1) PRIMARY KEY,
                session_id INTEGER,
                project_id INTEGER NOT NULL,
                run_token VARCHAR(255) NOT NULL,
                page_number INTEGER,
                source_page INTEGER DEFAULT 0,
                data_hash VARCHAR(64),
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
            )
        ''')
        print("   Created new table with correct schema")

        # Re-insert data if needed
        if has_data:
            # Note: ID will be auto-generated, SESSION_ID will be NULL
            print("   Re-inserting data...")
            for row in existing_data:
                cursor.execute('''
                    INSERT INTO scraped_records
                    (session_id, project_id, run_token, page_number, source_page, data_hash, data_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    None,  # Make session_id NULL
                    row.get('PROJECT_ID'),
                    row.get('RUN_TOKEN'),
                    row.get('PAGE_NUMBER'),
                    row.get('SOURCE_PAGE') or 0,
                    row.get('DATA_HASH'),
                    row.get('DATA_JSON'),
                    row.get('CREATED_AT')
                ))
            print(f"   Re-inserted {len(existing_data)} records")

        conn.commit()
        print("\n   Schema fix completed!")

    else:
        print("\n2. SESSION_ID is already nullable - no fix needed")

else:
    print("\n2. SESSION_ID column not found!")

# Step 3: Verify new schema
print("\n3. Verifying new schema...")
cursor.execute('''
    SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'SCRAPED_RECORDS'
    ORDER BY ORDINAL_POSITION
''', (db.sf_schema,))

new_columns = cursor.fetchall()
for col in new_columns:
    col_name = col.get('COLUMN_NAME') or col.get('column_name')
    nullable = col.get('IS_NULLABLE') or col.get('is_nullable')
    data_type = col.get('DATA_TYPE') or col.get('data_type')
    print(f"  - {col_name} ({data_type}) Nullable: {nullable}")

# Step 4: Test INSERT
print("\n4. Testing INSERT with NULL session_id...")
test_project_id = 77777
test_run_token = 'schema_test_123'

import json
from datetime import datetime

cursor.execute('''
    INSERT INTO scraped_records
    (session_id, project_id, run_token, page_number, source_page, data_json, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
''', (
    None,  # NULL session_id
    test_project_id,
    test_run_token,
    1,
    5,
    json.dumps({'test': 'schema_fix'}),
    datetime.now()
))
conn.commit()
print("   INSERT successful!")

# Verify
cursor.execute('SELECT COUNT(*) as cnt FROM scraped_records WHERE project_id = %s', (test_project_id,))
count = cursor.fetchone()
print(f"   Records found: {count}")

# Clean up
cursor.execute('DELETE FROM scraped_records WHERE project_id = %s', (test_project_id,))
conn.commit()
print("   Test data cleaned up")

conn.close()

print("\n" + "=" * 60)
print("SCHEMA FIX COMPLETED!")
print("=" * 60)
