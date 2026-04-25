"""
load_balancer.py — Predictive Load Balancer Service

Runs continuously every 5 seconds:
  1. Reads CPU / memory / process count
  2. Predicts load level (LOW / MEDIUM / HIGH) using ML model
  3. Stores metrics + prediction in MySQL
  4. Fetches metrics from all registered agent laptops
  5. Picks the least-loaded server and logs the decision

No nmap, no input() — runs silently in the background.
"""

import requests
import psutil
import joblib
import pandas as pd
import mysql.connector
import os
import time
from datetime import datetime

# ── Model ─────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "../ml/load_predictor.pkl")

if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
    print(f"Model loaded from {MODEL_PATH}")
else:
    print(f"ERROR: Model not found at {MODEL_PATH}")
    exit(1)

LOAD_MAP = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}

# ── DB helper ──────────────────────────────────────────────────
def db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="d1i2n3a4",
        database="load_balancer"
    )

# ── Get registered agents from controller ─────────────────────
def get_registered_devices():
    """Ask api.py for all registered devices."""
    try:
        r = requests.get("http://127.0.0.1:5000/devices", timeout=2)
        return r.json()          # list of { ip, name, online }
    except Exception:
        return []

# ── Main loop ─────────────────────────────────────────────────
def run_load_balancer():
    print("Starting Predictive Load Balancer Service...")
    print("-" * 50)

    while True:
        try:
            now = datetime.now()

            # ── 1. Local metrics ──────────────────────────────
            cpu      = psutil.cpu_percent(interval=1)
            memory   = psutil.virtual_memory().percent
            processes = len(psutil.pids())

            # ── 2. ML prediction ──────────────────────────────
            X = pd.DataFrame(
                [[cpu, memory, processes]],
                columns=["cpu", "memory", "processes"]
            )
            prediction    = model.predict(X)[0]
            predicted_load = LOAD_MAP.get(prediction, "LOW")

            print(f"[{now.strftime('%H:%M:%S')}] CPU: {cpu:.1f}% | Mem: {memory:.1f}% | Prediction: {predicted_load}")

            # ── 3. Store in DB ────────────────────────────────
            try:
                conn   = db()
                cursor = conn.cursor()

                # keep only last hour
                cursor.execute("DELETE FROM predictions    WHERE timestamp < NOW() - INTERVAL 1 HOUR")
                cursor.execute("DELETE FROM system_metrics WHERE timestamp < NOW() - INTERVAL 1 HOUR")

                cursor.execute(
                    "INSERT INTO system_metrics (timestamp, cpu, memory, processes) VALUES (%s, %s, %s, %s)",
                    (now, cpu, memory, processes)
                )
                cursor.execute(
                    "INSERT INTO predictions (timestamp, predicted_load) VALUES (%s, %s)",
                    (now, predicted_load)
                )
                conn.commit()
                conn.close()
            except Exception as db_err:
                print(f"  [DB ERROR] {db_err}")

            # ── 4. Fetch loads from all agent laptops ─────────
            devices = get_registered_devices()
            server_loads = {"LOCAL": cpu}

            for dev in devices:
                ip = dev.get("ip")
                if ip in ("local", None):
                    continue
                try:
                    data = requests.get(f"http://{ip}:6000/metrics", timeout=2).json()
                    server_loads[dev.get("name", ip)] = data.get("cpu", 100)
                except Exception:
                    server_loads[dev.get("name", ip)] = 100   # unreachable = worst

            # ── 5. Load balancing decision ────────────────────
            if server_loads:
                best = min(server_loads, key=server_loads.get)
                print(f"  → Route to: {best} (loads: {server_loads})")

        except Exception as e:
            print(f"[ERROR] {e}")

        print("-" * 50)
        time.sleep(5)   # run every 5 seconds

if __name__ == "__main__":
    run_load_balancer()