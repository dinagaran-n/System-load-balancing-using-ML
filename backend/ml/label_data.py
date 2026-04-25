import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="d1i2n3a4",
    database="load_balancer"
)

cursor = conn.cursor()

cursor.execute("SELECT id, cpu FROM system_metrics")
rows = cursor.fetchall()

for row in rows:
    id, cpu = row

    if cpu < 40:
        load = "LOW"
    elif cpu < 70:
        load = "MEDIUM"
    else:
        load = "HIGH"

    cursor.execute(
        "UPDATE system_metrics SET load_level = %s WHERE id = %s",
        (load, id)
    )

conn.commit()
conn.close()

print("Load levels assigned successfully")
