import sqlite3

conn = sqlite3.connect("system_metrics.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    cpu REAL,
    memory REAL,
    processes INTEGER
)
""")

conn.commit()
conn.close()

print("Database and table created successfully")
