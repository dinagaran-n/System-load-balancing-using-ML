"""
metrics_agent.py — Run this on any laptop you want to monitor.

HOW TO USE:
  1. Install dependencies (only needed once):
       pip install flask psutil requests

  2. Optionally set MY_NAME below to give this laptop a friendly label.
     If you leave it blank, the computer's hostname is used automatically.

  3. Run:
       python metrics_agent.py

  That's it! The agent automatically finds the controller on the same Wi-Fi.
  No IP address needed.
"""

from flask import Flask, jsonify
import psutil
import requests
import socket
import threading
import time

# ═══════════════════════════════════════════════════
#  OPTIONAL: give this laptop a friendly display name
#  Leave empty to use the computer's hostname
MY_NAME = ""
# ═══════════════════════════════════════════════════

BEACON_PORT    = 5001                   # must match controller
CONTROLLER_PORT = 5000
AGENT_PORT      = 6000
DISCOVER_TIMEOUT = 15                  # seconds to wait for controller beacon

app = Flask(__name__)

# ── Helpers ──────────────────────────────────────────────────

def get_my_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())

MY_IP       = get_my_ip()
MY_HOSTNAME = socket.gethostname()
MY_LABEL    = MY_NAME.strip() if MY_NAME.strip() else MY_HOSTNAME

# ── Auto-discover controller via UDP broadcast ────────────────

def discover_controller():
    """
    Listen for the controller's UDP beacon on the LAN.
    Returns the controller's IP address as a string.
    """
    print(f"[DISCOVER] Listening for controller beacon on UDP port {BEACON_PORT}…")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(DISCOVER_TIMEOUT)

    try:
        sock.bind(("", BEACON_PORT))
        data, addr = sock.recvfrom(1024)
        if b"LOAD_ENGINE_CONTROLLER" in data:
            controller_ip = addr[0]
            print(f"[DISCOVER] Found controller at {controller_ip}")
            return controller_ip
    except socket.timeout:
        print(f"[WARN] No controller found after {DISCOVER_TIMEOUT}s.")
        print("       Make sure the controller (api.py) is running on the same Wi-Fi.")
    except Exception as e:
        print(f"[WARN] Discovery error: {e}")
    finally:
        sock.close()

    return None

# ── Register with controller ──────────────────────────────────

def register(controller_ip):
    url = f"http://{controller_ip}:{CONTROLLER_PORT}/register"
    try:
        r = requests.post(url, json={
            "ip":       MY_IP,
            "name":     MY_LABEL,
            "hostname": MY_HOSTNAME
        }, timeout=5)
        print(f"[OK] Registered as '{MY_LABEL}' ({MY_IP}) → {controller_ip}")
        return True
    except Exception as e:
        print(f"[WARN] Could not register: {e}")
        return False

# ── Heartbeat (re-register every 30 s) ───────────────────────

def heartbeat_loop(controller_ip):
    while True:
        time.sleep(30)
        register(controller_ip)

# ── Flask routes (expose real-time metrics) ───────────────────

@app.route("/metrics")
def metrics():
    return jsonify({
        "cpu":       psutil.cpu_percent(interval=0.5),
        "memory":    psutil.virtual_memory().percent,
        "processes": len(psutil.pids()),
        "name":      MY_LABEL,
        "ip":        MY_IP,
        "hostname":  MY_HOSTNAME
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "name": MY_LABEL, "ip": MY_IP})

# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Load Engine — Metrics Agent")
    print(f"  Device name : {MY_LABEL}")
    print(f"  My IP       : {MY_IP}")
    print("=" * 50)

    controller_ip = discover_controller()

    if controller_ip:
        register(controller_ip)
        t = threading.Thread(target=heartbeat_loop, args=(controller_ip,), daemon=True)
        t.start()
    else:
        print("[ERROR] Could not find controller. Running in standalone mode.")
        print("        Metrics still available at http://0.0.0.0:6000/metrics")

    app.run(host="0.0.0.0", port=AGENT_PORT, debug=False)