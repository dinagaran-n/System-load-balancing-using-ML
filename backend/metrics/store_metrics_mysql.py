import psutil
import mysql.connector
import time
from datetime import datetime

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="d1i2n3a4",
    database="load_balancer"
)

cursor = conn.cursor()

while True:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    processes = len(psutil.pids())
    timestamp = datetime.now()

    cursor.execute(
        "INSERT INTO system_metrics (timestamp, cpu, memory, processes) VALUES (%s, %s, %s, %s)",
        (timestamp, cpu, memory, processes)
    )

    conn.commit()

    print("Saved:", timestamp, cpu, memory, processes)
    time.sleep(5)
