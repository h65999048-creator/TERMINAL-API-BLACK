import os
import json
import time
import threading
import asyncio
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS

import main as bot

app = Flask(__name__)
CORS(app)

# ==================== CONFIG ====================
API_KEY = os.environ.get("API_KEY", "CHANGE_THIS_SECRET_KEY_123")
PORT = int(os.environ.get("PORT", 5000))

# ==================== PROXY ====================
PROXY_USER = "hzmasuit"
PROXY_PASS = "u9tt9idxgjlv"

PROXY_LIST = [
    "45.38.107.97:6014",
    "64.137.96.74:6641",
    "198.23.243.226:6361",
    "38.154.185.97:6370",
    "84.247.60.125:6095",
    "191.96.254.138:6185",
    "198.46.161.42:5092",
    "64.137.10.153:5803",
    "104.164.49.38:7693",
    "23.26.71.145:5628",
]

PROXIES = [f"http://{PROXY_USER}:{PROXY_PASS}@{p}" for p in PROXY_LIST]

_proxy_index = 0
_proxy_lock = threading.Lock()

def get_next_proxy():
    global _proxy_index
    with _proxy_lock:
        p = PROXIES[_proxy_index % len(PROXIES)]
        _proxy_index += 1
        return p

# ==================== AUTH ====================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ==================== ROUTES ====================
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "success": True,
        "service": "Blacklist API",
        "total_proxies": len(PROXIES),
        "status": "online",
        "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "success": True,
        "status": "healthy",
        "total_proxies": len(PROXIES),
    })

@app.route("/api/blacklist", methods=["POST"])
@require_api_key
def api_blacklist():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    if not email:
        return jsonify({"success": False, "error": "email required"}), 400
    if not bot.is_valid_email(email):
        return jsonify({"success": False, "error": "Invalid email", "email": email}), 400
    try:
        success, result = bot.blacklist_email(email, is_auto=False)
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "email": email}), 500
    return jsonify({
        "success": bool(success),
        "email": email,
        "message": result,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# ==================== RUN ====================
def run_flask():
    try:
        print(f"[+] Proxy API on port {PORT}")
        print(f"[+] {len(PROXIES)} proxies loaded")
        app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)
    except Exception as e:
        print(f"[!] Flask error: {e}")

if __name__ == "__main__":
    # Flask ko daemon thread me chalao (background)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Bot ko MAIN THREAD me chalao (run_polling ke liye zaroori)
    print("[+] Starting bot in main thread...")
    try:
        bot.main()
    except Exception as e:
        print(f"[!] Bot error: {e}")
