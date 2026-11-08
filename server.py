"""
Render Cloud Runner & Remote Task Server
A high-performance remote compute bridge allowing authenticated execution
of Python scripts, background jobs, and automation directly on Render.
"""

import os
import sys
import time
import subprocess
import platform
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Authentication Secret
RUNNER_SECRET = os.environ.get("RUNNER_SECRET_KEY", "antigravity_cloud_master_2026")
PORT = int(os.environ.get("PORT", 5050))
START_TIME = time.time()


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
    return render_template("dashboard.html", stats=stats, secret=RUNNER_SECRET)


@app.route("/api/health", methods=["GET"])
def health():
    """Public health check."""
    return jsonify({
        "status": "online",
        "service": "render-cloud-runner",
        "system": get_system_stats()
    })


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
            # Run inline python code
            cmd = [sys.executable, "-c", code]
        else:
            # Run bash shell command
            cmd = ["/bin/bash", "-c", code]

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd="/tmp"
        )
        duration = round(time.time() - start_exec, 3)

        return jsonify({
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "execution_time_sec": duration,
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": f"Execution timed out after {timeout} seconds.",
            "execution_time_sec": timeout,
        }), 408
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "execution_time_sec": round(time.time() - start_exec, 3),
        }), 500


@app.route("/api/clone_and_run", methods=["POST"])
def clone_and_run():
    """Clone a GitHub repository and run a background task."""
    if not check_auth():
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    repo_url = data.get("repo_url", "").strip()
    run_cmd = data.get("cmd", "python3 main.py").strip()

    if not repo_url:
        return jsonify({"error": "repo_url required"}), 400

    repo_name = repo_url.split("/")[-1].replace(".git", "")
    target_dir = f"/tmp/{repo_name}_{int(time.time())}"

    # Clone
    clone_cmd = f"git clone --depth 1 {repo_url} {target_dir} && cd {target_dir} && {run_cmd}"
    try:
        proc = subprocess.run(
            ["/bin/bash", "-c", clone_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120
        )
        return jsonify({
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "target_dir": target_dir
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"[*] Starting Render Cloud Runner on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
