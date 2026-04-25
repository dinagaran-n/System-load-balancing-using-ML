import psutil
import time

while True:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    processes = len(psutil.pids())

    print("CPU Usage:", cpu, "%")
    print("Memory Usage:", memory, "%")
    print("Running Processes:", processes)
    print("-" * 30)

    time.sleep(2)
