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
import fcntl
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
# 24/7 BACKGROUND FACEBOOK AI BOT SUBPROCESS (AUTO-RESTARTING WATCHDOG)
# ─────────────────────────────────────────────────────────────────────────────
BOT_PROCESS = None
BOT_LOG_FILE = "/tmp/bot_runner.log"
HEARTBEAT_FILE = "/tmp/bot_heartbeat.txt"
_BOT_ERROR = None

def get_bot_heartbeat_age() -> float:
    """Return seconds since last heartbeat write, or -1 if none."""
    if os.path.exists(HEARTBEAT_FILE):
        try:
            with open(HEARTBEAT_FILE, "r") as f:
                val = float(f.read().strip())
                return max(0.0, time.time() - val)
        except Exception:
            pass
    return -1.0

def is_bot_active() -> bool:
    """Check if bot subprocess is alive and sending heartbeats."""
    global BOT_PROCESS
    if BOT_PROCESS is None or BOT_PROCESS.poll() is not None:
        return False
    age = get_bot_heartbeat_age()
    if age >= 0 and age > 35.0:
        return False
    return True

def ensure_bot_running():
    """Ensure bot subprocess is alive and responsive. Restart if dead or stalled."""
    global BOT_PROCESS, _BOT_ERROR
    if BOT_PROCESS is not None:
        if BOT_PROCESS.poll() is None:
            age = get_bot_heartbeat_age()
            if age >= 0 and age > 35.0:
                logger.warning(f"⚠️ Bot heartbeat stalled ({age:.1f}s ago). Terminating PID {BOT_PROCESS.pid}...")
                try:
                    BOT_PROCESS.kill()
                    BOT_PROCESS.wait(timeout=3)
                except Exception:
                    pass
                BOT_PROCESS = None
            else:
                return  # Bot is alive and healthy
        else:
            logger.warning(f"⚠️ Bot process exited with code {BOT_PROCESS.returncode}. Restarting...")
            BOT_PROCESS = None

    try:
        logger.info("🚀 Launching fast_messenger_bot.py as dedicated background subprocess...")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fast_messenger_bot.py")
        log_fp = open(BOT_LOG_FILE, "a+", buffering=1)
        BOT_PROCESS = subprocess.Popen(
            [sys.executable, "-u", script_path],
            stdout=log_fp,
            stderr=log_fp,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        logger.info(f"✅ Bot background worker started with PID {BOT_PROCESS.pid}")
        _BOT_ERROR = None
    except Exception as e:
        _BOT_ERROR = str(e)
        logger.error(f"❌ Failed to launch bot subprocess: {e}", exc_info=True)

def _watchdog_loop():
    """Continuous background supervisor thread checking health every 10 seconds."""
    time.sleep(3)
    while True:
        try:
            ensure_bot_running()
        except Exception as e:
            logger.error(f"Watchdog exception: {e}")
        time.sleep(10)

# Start watchdog thread in current process
threading.Thread(target=_watchdog_loop, daemon=True, name="BotWatchdog").start()

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
    bot_alive = is_bot_active()
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
    bot_alive = is_bot_active()
    return jsonify({
        "status": "online",
        "service": "facebook-ai-commander-bot",
        "bot_worker": "active" if bot_alive else "crashed",
        "bot_pid": BOT_PROCESS.pid if BOT_PROCESS and BOT_PROCESS.poll() is None else None,
        "bot_heartbeat_age_sec": round(get_bot_heartbeat_age(), 1),
        "bot_error": _BOT_ERROR,
        "page_name": "AI Commander Bot",
        "page_id": "1489379004255673",
        "uptimerobot_keepalive_target": "https://render-cloud-runner.onrender.com/api/health",
        "system": get_system_stats()
    }), 200

@app.route("/api/bot/logs", methods=["GET"])
def bot_logs():
    """Retrieve the last 150 lines of bot logs."""
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    lines = []
    if os.path.exists(BOT_LOG_FILE):
        try:
            with open(BOT_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-150:]
        except Exception as e:
            lines = [f"Error reading log: {e}"]
    return "".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}

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
