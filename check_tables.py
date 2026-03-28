import sqlite3
conn = sqlite3.connect('parsehub.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for t in cursor.fetchall():
    print(f"  - {t[0]}")
conn.close()
