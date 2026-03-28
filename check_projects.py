import sqlite3
conn = sqlite3.connect('parsehub.db')
cursor = conn.cursor()
cursor.execute("SELECT id, token, title FROM projects LIMIT 10")
for r in cursor.fetchall():
    print(f"ID:{r[0]} Token:{r[1][:15]} Title:{r[2][:30]}")
conn.close()
