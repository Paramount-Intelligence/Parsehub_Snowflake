"""Test the actual persist_results method"""
import sys
import os

os.chdir('d:/Parsehub-Snowflake/Parsehub_Snowflake/backend')
sys.path.insert(0, 'd:/Parsehub-Snowflake/Parsehub_Snowflake/backend')

from dotenv import load_dotenv
load_dotenv()

from src.services.metadata_driven_resume_scraper import get_metadata_driven_scraper

print("=" * 60)
print("TESTING persist_results METHOD")
print("=" * 60)

scraper = get_metadata_driven_scraper()
print(f"Scraper initialized: {type(scraper).__name__}")
print(f"Database: {scraper.db.sf_database}")

# Create test data
test_project_id = 66666
test_run_token = "test_run_token_789"
test_source_page = 10
test_data = [
    {"product": "Test Product 1", "price": "15.00", "brand": "Brand A"},
    {"product": "Test Product 2", "price": "25.00", "brand": "Brand B"},
    {"product": "Test Product 3", "price": "35.00", "brand": "Brand C"},
]

print(f"\nCalling persist_results:")
print(f"  - project_id: {test_project_id}")
print(f"  - run_token: {test_run_token}")
print(f"  - source_page: {test_source_page}")
print(f"  - session_id: None")
print(f"  - data: {len(test_data)} records")

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

if success:
    print("\n✓ persist_results: SUCCESS")

    # Verify in database
    conn = scraper.db.connect()
    cursor = scraper.db.cursor()
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM scraped_records WHERE project_id = %s",
        (test_project_id,)
    )
    count = cursor.fetchone()
    print(f"\nVerified in database: {count} records")

    # Clean up
    cursor.execute(
        "DELETE FROM scraped_records WHERE project_id = %s",
        (test_project_id,)
    )
    conn.commit()
    conn.close()
    print("Test data cleaned up")

    print("\n" + "=" * 60)
    print("persist_results TEST: PASSED")
    print("=" * 60)
else:
    print("\n✗ persist_results: FAILED")
    print("No records were inserted!")
