"""Test Snowflake INSERT with proper venv312"""
import sys
import os

os.chdir('d:/Parsehub-Snowflake/Parsehub_Snowflake/backend')
sys.path.insert(0, 'd:/Parsehub-Snowflake/Parsehub_Snowflake/backend')

from dotenv import load_dotenv
load_dotenv()

from src.models.database import ParseHubDatabase
import json
from datetime import datetime

db = ParseHubDatabase()
conn = db.connect()
cursor = db.cursor()

# Check if table exists
cursor.execute('''
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'SCRAPED_RECORDS'
''', (db.sf_schema,))

table = cursor.fetchone()
if table:
    print('Table SCRAPED_RECORDS exists in Snowflake')

    # Check columns
    cursor.execute('''
        SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'SCRAPED_RECORDS'
        ORDER BY ORDINAL_POSITION
    ''', (db.sf_schema,))

    print('Columns:')
    for col in cursor.fetchall():
        # Keys may be lowercase
        col_name = col.get('COLUMN_NAME') or col.get('column_name')
        col_type = col.get('DATA_TYPE') or col.get('data_type')
        nullable = col.get('IS_NULLABLE') or col.get('is_nullable')
        print(f'  - {col_name} ({col_type}) Nullable: {nullable}')

    # Test INSERT
    print()
    print('Testing INSERT with NULL session_id...')
    test_project_id = 88888
    test_run_token = 'test_run_123'

    try:
        cursor.execute('''
            INSERT INTO scraped_records
            (session_id, project_id, run_token, page_number, source_page, data_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            None,  # NULL session_id
            test_project_id,
            test_run_token,
            1,  # page_number
            5,  # source_page
            json.dumps({'test': 'data'}),
            datetime.now()
        ))
        conn.commit()
        print('INSERT successful!')

        # Verify
        cursor.execute('SELECT COUNT(*) as cnt FROM scraped_records WHERE project_id = %s', (test_project_id,))
        count = cursor.fetchone()
        print(f'Records for test project: {count}')

        # Clean up
        cursor.execute('DELETE FROM scraped_records WHERE project_id = %s', (test_project_id,))
        conn.commit()
        print('Test data cleaned up')
        print()
        print('=' * 60)
        print('Snowflake INSERT test: PASSED')
        print('=' * 60)

    except Exception as e:
        print(f'INSERT FAILED: {e}')
        import traceback
        traceback.print_exc()
        conn.rollback()
else:
    print('Table SCRAPED_RECORDS does NOT exist in Snowflake!')

conn.close()
