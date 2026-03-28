"""
Diagnostic script to test Snowflake data insertion
Run this to identify why scraped data isn't persisting
"""
import os
import sys
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

def test_snowflake_connection():
    """Test basic Snowflake connectivity"""
    print("=" * 70)
    print("TEST 1: Snowflake Connection")
    print("=" * 70)
    
    try:
        from src.models.database import ParseHubDatabase
        db = ParseHubDatabase()
        print(f"✓ Database initialized: {db.sf_account}.{db.sf_database}.{db.sf_schema}")
        
        # Test connection
        conn = db.connect()
        print(f"✓ Connection established: {type(conn)}")
        
        # Test cursor
        cursor = db.cursor()
        print(f"✓ Cursor created: {type(cursor)}")
        
        # Test simple query
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()
        print(f"✓ Snowflake version: {version}")
        
        conn.close()
        print("✓ Connection closed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_table_exists():
    """Test if scraped_records table exists"""
    print("\n" + "=" * 70)
    print("TEST 2: Check scraped_records Table")
    print("=" * 70)
    
    try:
        from src.models.database import ParseHubDatabase
        db = ParseHubDatabase()
        conn = db.connect()
        cursor = db.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'SCRAPED_RECORDS'
        """, (db.sf_schema,))
        
        result = cursor.fetchone()
        if result:
            print(f"✓ Table SCRAPED_RECORDS exists in schema {db.sf_schema}")
        else:
            print(f"✗ Table SCRAPED_RECORDS NOT FOUND in schema {db.sf_schema}")
            print("  Available tables:")
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME
            """, (db.sf_schema,))
            for row in cursor.fetchall():
                print(f"    - {row['TABLE_NAME']}")
        
        conn.close()
        return result is not None
        
    except Exception as e:
        print(f"✗ Table check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_column_nullable():
    """Test if session_id column is nullable"""
    print("\n" + "=" * 70)
    print("TEST 3: Check session_id Column (Nullable)")
    print("=" * 70)
    
    try:
        from src.models.database import ParseHubDatabase
        db = ParseHubDatabase()
        conn = db.connect()
        cursor = db.cursor()
        
        # Check column definition
        cursor.execute("""
            SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'SCRAPED_RECORDS' 
            AND COLUMN_NAME = 'SESSION_ID'
        """, (db.sf_schema,))
        
        result = cursor.fetchone()
        if result:
            print(f"✓ Column found:")
            print(f"  - Name: {result['COLUMN_NAME']}")
            print(f"  - Nullable: {result['IS_NULLABLE']}")
            print(f"  - Type: {result['DATA_TYPE']}")
            
            if result['IS_NULLABLE'] == 'YES':
                print("  ✓ session_id is nullable - GOOD")
                return True
            else:
                print("  ✗ session_id is NOT nullable - THIS IS THE PROBLEM!")
                return False
        else:
            print("✗ Column SESSION_ID not found")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Column check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_actual_insert():
    """Test actual INSERT operation with NULL session_id"""
    print("\n" + "=" * 70)
    print("TEST 4: Test Actual INSERT (with NULL session_id)")
    print("=" * 70)
    
    try:
        from src.models.database import ParseHubDatabase
        db = ParseHubDatabase()
        conn = db.connect()
        cursor = db.cursor()
        
        # Create test data
        test_project_id = 99999  # Test project ID
        test_run_token = "test_run_token_123"
        test_source_page = 1
        test_data = {"test": "data", "timestamp": str(datetime.now())}
        
        print(f"Inserting test record:")
        print(f"  - project_id: {test_project_id}")
        print(f"  - run_token: {test_run_token}")
        print(f"  - source_page: {test_source_page}")
        print(f"  - session_id: NULL")
        
        try:
            cursor.execute('''
                INSERT INTO scraped_records 
                (session_id, project_id, run_token, source_page, data_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                None,  # session_id = NULL
                test_project_id,
                test_run_token,
                test_source_page,
                json.dumps(test_data),
                datetime.now()
            ))
            
            conn.commit()
            print("✓ INSERT successful!")
            
            # Verify insert
            cursor.execute("""
                SELECT COUNT(*) as cnt 
                FROM scraped_records 
                WHERE project_id = %s AND run_token = %s
            """, (test_project_id, test_run_token))
            
            result = cursor.fetchone()
            count = result['CNT'] if result else 0
            print(f"✓ Verified: {count} record(s) found in database")
            
            # Clean up test data
            cursor.execute("""
                DELETE FROM scraped_records 
                WHERE project_id = %s AND run_token = %s
            """, (test_project_id, test_run_token))
            conn.commit()
            print("✓ Test data cleaned up")
            
            conn.close()
            return True
            
        except Exception as insert_err:
            conn.rollback()
            print(f"✗ INSERT FAILED: {insert_err}")
            import traceback
            traceback.print_exc()
            conn.close()
            return False
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_persist_results_method():
    """Test the actual persist_results method"""
    print("\n" + "=" * 70)
    print("TEST 5: Test persist_results Method")
    print("=" * 70)
    
    try:
        from src.services.metadata_driven_resume_scraper import get_metadata_driven_scraper
        
        scraper = get_metadata_driven_scraper()
        print(f"✓ Scraper initialized")
        print(f"  - Database type: {type(scraper.db)}")
        print(f"  - Snowflake account: {scraper.db.sf_account}")
        
        # Create test data
        test_project_id = 99998
        test_run_token = "test_run_token_456"
        test_source_page = 5
        test_data = [
            {"product": "Test 1", "price": "10.00"},
            {"product": "Test 2", "price": "20.00"},
        ]
        
        print(f"\nCalling persist_results with:")
        print(f"  - project_id: {test_project_id}")
        print(f"  - run_token: {test_run_token}")
        print(f"  - source_page: {test_source_page}")
        print(f"  - session_id: None")
        print(f"  - data: {len(test_data)} records")
        
        # Call the actual method
        success, inserted_count, highest_page = scraper.persist_results(
            project_id=test_project_id,
            run_token=test_run_token,
            data=test_data,
            source_page=test_source_page,
            session_id=None
        )
        
        print(f"\nResult:")
        print(f"  - success: {success}")
        print(f"  - inserted_count: {inserted_count}")
        print(f"  - highest_page: {highest_page}")
        
        if success and inserted_count > 0:
            print("✓ persist_results SUCCESS")
            
            # Clean up
            conn = scraper.db.connect()
            cursor = scraper.db.cursor()
            cursor.execute("""
                DELETE FROM scraped_records 
                WHERE project_id = %s AND run_token = %s
            """, (test_project_id, test_run_token))
            conn.commit()
            conn.close()
            print("✓ Test data cleaned up")
            
            return True
        else:
            print("✗ persist_results FAILED - No records inserted")
            return False
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("SNOWFLAKE DATA PERSISTENCE DIAGNOSTIC")
    print("=" * 70)
    
    results = []
    
    results.append(("Connection", test_snowflake_connection()))
    results.append(("Table Exists", test_table_exists()))
    results.append(("Column Nullable", test_column_nullable()))
    results.append(("Direct INSERT", test_actual_insert()))
    results.append(("persist_results Method", test_persist_results_method()))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("ALL TESTS PASSED - Data persistence should work!")
    else:
        print("SOME TESTS FAILED - See above for details")
    print("=" * 70)
