from flask import Flask, jsonify, send_from_directory, request
import mysql.connector
import os
import psutil
import requests
import socket
import threading
import time
from datetime import datetime

# ── UDP broadcast beacon ─────────────────────────────────────
# Announces controller IP on LAN so agents can auto-discover
BEACON_PORT    = 5001
BEACON_MESSAGE = b"LOAD_ENGINE_CONTROLLER"

def broadcast_beacon():
    """Broadcast this controller's IP every 3 seconds."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while True:
        try:
            sock.sendto(BEACON_MESSAGE, ("255.255.255.255", BEACON_PORT))
        except Exception:
            pass
        time.sleep(3)

# ── paths ───────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR)

# ── in-memory device registry ───────────────────────────────
# { ip: { "name": str, "hostname": str, "registered_at": str, "last_seen": str } }
device_registry = {}

# ── DB helper ────────────────────────────────────────────────
def db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="d1i2n3a4",
        database="load_balancer"
    )

# ── static files ─────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/charts.js")
def charts_js():
    return send_from_directory(FRONTEND_DIR, "charts.js")

@app.route("/style.css")
def style_css():
    return send_from_directory(FRONTEND_DIR, "style.css")

# ── /register  (called by metrics_agent.py on each laptop) ───
@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    ip       = data.get("ip", request.remote_addr)
    name     = data.get("name", ip)          # human display name
    hostname = data.get("hostname", ip)

    now = datetime.now().strftime("%H:%M:%S")

    if ip not in device_registry:
        device_registry[ip] = {
            "name": name,
            "hostname": hostname,
            "registered_at": now,
            "last_seen": now
        }
    else:
        device_registry[ip]["last_seen"] = now
        # allow name update
        if name != ip:
            device_registry[ip]["name"] = name

    print(f"[REGISTER] {name} ({ip}) at {now}")
    return jsonify({"status": "registered", "ip": ip})

# ── /devices  (returns list of all connected laptops) ────────
@app.route("/devices")
def devices():
    result = []
    for ip, info in device_registry.items():
        # quick reachability ping to mark online/offline
        online = False
        try:
            r = requests.get(f"http://{ip}:6000/metrics", timeout=1.5)
            online = r.status_code == 200
            device_registry[ip]["last_seen"] = datetime.now().strftime("%H:%M:%S")
        except Exception:
            pass

        result.append({
            "ip": ip,
            "name": info["name"],
            "hostname": info["hostname"],
            "registered_at": info["registered_at"],
            "last_seen": info["last_seen"],
            "online": online
        })

    return jsonify(result)

# ── /node-metrics/<ip>  (proxy: fetch live metrics from agent) ─
@app.route("/node-metrics/<path:ip>")
def node_metrics(ip):
    # Special key "local" means this machine itself
    if ip == "local":
        cpu    = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory().percent
        procs  = len(psutil.pids())
        return jsonify({
            "cpu": cpu,
            "memory": memory,
            "processes": procs,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "source": "local"
        })

    try:
        r = requests.get(f"http://{ip}:6000/metrics", timeout=3)
        data = r.json()
        data["timestamp"] = datetime.now().strftime("%H:%M:%S")
        data["source"] = ip
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e), "cpu": 0, "memory": 0, "processes": 0,
                        "timestamp": datetime.now().strftime("%H:%M:%S")}), 502

# ── /predicted-load  (existing — uses DB) ────────────────────
@app.route("/predicted-load")
def predicted_load():
    try:
        conn = db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT p.timestamp, p.predicted_load, s.cpu
            FROM predictions p
            INNER JOIN system_metrics s ON p.timestamp = s.timestamp
            ORDER BY p.timestamp DESC
            LIMIT 25
        """)
        rows = cur.fetchall()
        conn.close()

        def get_load_level(cpu):
            if cpu is None: return "N/A"
            if cpu < 40:    return "LOW"
            if cpu < 70:    return "MEDIUM"
            return "HIGH"

        return jsonify([
            {
                "time":      r[0].strftime("%H:%M:%S") if hasattr(r[0], "strftime") else str(r[0]),
                "predicted": r[1],
                "actual":    get_load_level(r[2]),
                "cpu":       r[2]
            }
            for r in rows[::-1]
        ])
    except Exception as e:
        # fallback if DB unavailable
        return jsonify([]), 200

# ── /server-allocation ───────────────────────────────────────
@app.route("/server-allocation")
def server_allocation():
    try:
        # Get the latest CPU load from psutil to dictate allocation level
        cpu = psutil.cpu_percent(interval=0.1)
        
        load_level = "LOW"
        if cpu >= 70:
            load_level = "HIGH"
        elif cpu >= 40:
            load_level = "MEDIUM"

        servers = []
        if load_level == "LOW":
            servers = [
                { "id": "A", "name": "Server Alpha", "processes": ["nginx", "api-gateway", "auth-svc", "db-primary", "cache-redis", "payment-svc"], "load_pct": max(5, int(cpu)) },
                { "id": "B", "name": "Server Beta",  "processes": [], "load_pct": 0 },
                { "id": "C", "name": "Server Gamma", "processes": [], "load_pct": 0 }
            ]
        elif load_level == "MEDIUM":
            servers = [
                { "id": "A", "name": "Server Alpha", "processes": ["nginx", "api-gateway", "auth-svc"], "load_pct": int(cpu * 0.6) },
                { "id": "B", "name": "Server Beta",  "processes": ["db-primary", "cache-redis", "payment-svc"], "load_pct": int(cpu * 0.4) },
                { "id": "C", "name": "Server Gamma", "processes": [], "load_pct": 0 }
            ]
        else: # HIGH
             servers = [
                { "id": "A", "name": "Server Alpha", "processes": ["nginx", "api-gateway"], "load_pct": int(cpu * 0.45) },
                { "id": "B", "name": "Server Beta",  "processes": ["auth-svc", "payment-svc"], "load_pct": int(cpu * 0.35) },
                { "id": "C", "name": "Server Gamma", "processes": ["db-primary", "cache-redis"], "load_pct": int(cpu * 0.20) }
            ]

        return jsonify({
            "load_level": load_level,
            "servers": servers
        })
    except Exception as e:
        return jsonify({"error": str(e), "load_level": "LOW", "servers": []}), 500

# ── /current-metrics  (this machine — legacy compat) ─────────
@app.route("/current-metrics")
def current_metrics():
    cpu    = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory().percent
    procs  = len(psutil.pids())
    return jsonify({
        "cpu":       cpu,
        "memory":    memory,
        "processes": procs,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

# ── main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    # auto-register this machine
    my_name = socket.gethostname()
    device_registry["local"] = {
        "name":          f"My Laptop ({my_name})",
        "hostname":      my_name,
        "registered_at": datetime.now().strftime("%H:%M:%S"),
        "last_seen":     datetime.now().strftime("%H:%M:%S")
    }

    # start UDP beacon so agents can auto-discover this controller
    beacon_thread = threading.Thread(target=broadcast_beacon, daemon=True)
    beacon_thread.start()
    print(f"[BOOT] Controller online. Broadcasting beacon on UDP port {BEACON_PORT}.")

    app.run(host="0.0.0.0", debug=False, port=5000)
