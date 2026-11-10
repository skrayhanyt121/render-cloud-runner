"""
Render Cloud Runner & Facebook AI Commander Bot Server
A high-performance remote compute bridge and 24/7 autonomous Facebook AI bot
deployed directly on Render with UptimeRobot continuous keep-alive.
"""

import os
import sys
import time
import subprocess
import platform
import logging
import threading
from flask import Flask, request, jsonify, render_template
from bundle_manager import unpack_bundle

# Unpack bundled credentials if running in a fresh container (e.g. Render)
unpack_bundle()

# Synchronously import bot engine before spawning thread to avoid import race conditions
import fast_messenger_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RenderServer")

app = Flask(__name__)

# Authentication Secret
RUNNER_SECRET = os.environ.get("RUNNER_SECRET_KEY", "antigravity_cloud_master_2026")
PORT = int(os.environ.get("PORT", 5050))
START_TIME = time.time()

# ─────────────────────────────────────────────────────────────────────────────
# 24/7 BACKGROUND FACEBOOK AI BOT WORKER
# ─────────────────────────────────────────────────────────────────────────────
_BOT_THREAD = None
_BOT_ENGINE = None
_BOT_ERROR = None

def run_facebook_bot():
    global _BOT_ENGINE, _BOT_ERROR
    logger.info("🚀 Launching FastMessengerEngine inside Render background thread...")
    try:
        _BOT_ENGINE = fast_messenger_bot.FastMessengerEngine()
        logger.info("✅ FastMessengerEngine initialized successfully! Starting polling loop...")
        _BOT_ENGINE.run_forever()
    except Exception as e:
        _BOT_ERROR = str(e)
        logger.error(f"❌ Facebook Bot Worker crashed: {e}", exc_info=True)

def ensure_bot_running():
    global _BOT_THREAD
    if _BOT_THREAD is None or not _BOT_THREAD.is_alive():
        _BOT_THREAD = threading.Thread(target=run_facebook_bot, daemon=True, name="FacebookBotWorker")
        _BOT_THREAD.start()
        logger.info("Started FacebookBotWorker daemon thread.")

# Auto-start bot on server initialization
ensure_bot_running()

def check_auth():
    """Verify request authorization."""
    token = request.headers.get("X-Runner-Secret") or request.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        token = token[7:]
    return token == RUNNER_SECRET

def get_system_stats():
    """Gather system metrics (RAM, OS, CPU, Uptime)."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=None)
        disk = psutil.disk_usage("/")
        return {
            "ram_total_mb": round(mem.total / (1024 * 1024), 1),
            "ram_used_mb": round(mem.used / (1024 * 1024), 1),
            "ram_pct": mem.percent,
            "cpu_pct": cpu_pct,
            "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
            "uptime_seconds": int(time.time() - START_TIME),
            "python_version": sys.version.split()[0],
            "os": f"{platform.system()} {platform.release()}",
        }
    except Exception:
        return {
            "ram_total_mb": "512 MB (Render Free)",
            "ram_used_mb": "N/A",
            "ram_pct": "N/A",
            "cpu_pct": "N/A",
            "disk_free_gb": "N/A",
            "uptime_seconds": int(time.time() - START_TIME),
            "python_version": sys.version.split()[0],
            "os": f"{platform.system()} {platform.release()}",
        }

@app.route("/")
def index():
    """Server status & test interface."""
    stats = get_system_stats()
    ensure_bot_running()
    bot_alive = _BOT_THREAD is not None and _BOT_THREAD.is_alive()
    return render_template(
        "dashboard.html",
        stats=stats,
        secret=RUNNER_SECRET,
        bot_alive=bot_alive,
        bot_error=_BOT_ERROR
    )

@app.route("/api/health", methods=["GET"])
def health():
    """Public health check endpoint designed specifically for UptimeRobot."""
    ensure_bot_running()
    bot_alive = _BOT_THREAD is not None and _BOT_THREAD.is_alive()
    return jsonify({
        "status": "online",
        "service": "facebook-ai-commander-bot",
        "bot_worker": "active" if bot_alive else "crashed",
        "bot_error": _BOT_ERROR,
        "page_name": "AI Commander Bot",
        "page_id": "1489379004255673",
        "uptimerobot_keepalive_target": "https://render-cloud-runner.onrender.com/api/health",
        "system": get_system_stats()
    }), 200

@app.route("/api/ping", methods=["GET"])
def ping():
    """Ultra-fast lightweight ping."""
    return "pong", 200

@app.route("/api/execute", methods=["POST"])
def execute():
    """Execute shell command or python script in cloud environment."""
    if not check_auth():
        return jsonify({"error": "Unauthorized. Provide valid X-Runner-Secret header."}), 401

    data = request.get_json(silent=True) or {}
    exec_type = data.get("type", "shell").lower()
    code = data.get("code", "").strip()
    timeout = min(int(data.get("timeout", 60)), 300)

    if not code:
        return jsonify({"error": "No code provided to execute."}), 400

    start_exec = time.time()
    try:
        if exec_type == "python":
            cmd = [sys.executable, "-c", code]
        else:
            cmd = ["/bin/bash", "-c", code]

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(__file__)
        )

        return jsonify({
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "execution_time_sec": round(time.time() - start_exec, 3),
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "error": f"Command timed out after {timeout} seconds.",
            "execution_time_sec": round(time.time() - start_exec, 3),
        }), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
