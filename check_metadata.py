import sqlite3
conn = sqlite3.connect('parsehub.db')
cursor = conn.cursor()
cursor.execute("SELECT id, project_name, total_pages, status FROM metadata WHERE total_pages > 0")
for r in cursor.fetchall():
    print(f"ID:{r[0]} Name:{r[1][:35]} Pages:{r[2]} Status:{r[3]}")
conn.close()
