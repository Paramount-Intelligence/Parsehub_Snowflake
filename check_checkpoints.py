import sqlite3
conn = sqlite3.connect('parsehub.db')
cursor = conn.cursor()
cursor.execute("SELECT project_id, MAX(source_page), COUNT(*) FROM scraped_records GROUP BY project_id")
print("ProjectID | HighestPageScraped | TotalRecords")
for r in cursor.fetchall():
    print(f"   {r[0]:3}    |        {r[1]:3}        |     {r[2]:4}")
conn.close()
