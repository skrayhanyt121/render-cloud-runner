import os
import json
import logging
import subprocess
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("CodespaceCluster")

POOL_PATH = os.path.join(os.path.dirname(__file__), "codespaces_pool.json")

class CodespaceClusterManager:
    def __init__(self, config_path: str = POOL_PATH):
        self.config_path = config_path
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading codespaces pool: {e}")
        return {"accounts": [], "active_index": 0}

    def _save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving codespaces pool: {e}")

    def get_accounts(self):
        return self.data.get("accounts", [])

    def get_active_account(self) -> Optional[Dict[str, Any]]:
        accs = self.get_accounts()
        idx = self.data.get("active_index", 0)
        if 0 <= idx < len(accs):
            return accs[idx]
        return accs[0] if accs else None

    def switch_account(self, index: int) -> Tuple[bool, str]:
        accs = self.get_accounts()
        if 0 <= index < len(accs):
            self.data["active_index"] = index
            self._save()
            acc = accs[index]
            return True, f"✅ Switched active Codespace to Account #{index + 1}: {acc.get('username')}"
        return False, f"❌ Invalid account index {index}. Total accounts: {len(accs)}"

    def run_command(self, cmd: str, timeout: int = 60) -> Tuple[int, str]:
        """Runs a bash command in the active codespace via gh cs ssh"""
        acc = self.get_active_account()
        if not acc:
            return 1, "❌ No active Codespace account configured."

        token = acc.get("token")
        env = os.environ.copy()
        env["GH_TOKEN"] = token

        # If codespace name is known or we let gh pick the default for this user
        cs_name = acc.get("codespace_name", "cloud-browser-jrwpgvx5r4cqg6p")

        cli_cmd = ["gh", "cs", "ssh", "-c", cs_name, "--", cmd]
        try:
            proc = subprocess.run(
                cli_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            # Filter out gh progress spinner lines
            clean_lines = [
                line for line in stdout.splitlines()
                if not line.startswith("Connecting to codespace") and not line.startswith("Fetching SSH Details")
            ]
            clean_out = "\n".join(clean_lines).strip()

            if proc.returncode == 0:
                return 0, clean_out or "Command executed successfully (no stdout)."
            else:
                return proc.returncode, clean_out or stderr or f"Process exited with code {proc.returncode}"
        except subprocess.TimeoutExpired:
            return -1, f"⏱️ Remote command timed out after {timeout} seconds."
        except Exception as e:
            return -1, f"❌ Execution error: {e}"

    def get_state(self) -> str:
        """Fast state check via GitHub REST API (0.5s)"""
        import urllib.request
        acc = self.get_active_account()
        if not acc:
            return "Unknown"
        token = acc.get("token")
        cs_name = acc.get("codespace_name", "cloud-browser-jrwpgvx5r4cqg6p")
        try:
            req = urllib.request.Request(f"https://api.github.com/user/codespaces/{cs_name}")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("User-Agent", "Mozilla/5.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return data.get("state", "Unknown")
        except Exception as e:
            return "Offline"

    def stop_codespace(self) -> Tuple[bool, str]:
        """Safely shutdown active codespace to save monthly compute quota"""
        import urllib.request, urllib.error
        acc = self.get_active_account()
        if not acc:
            return False, "❌ No active Codespace account configured."
        token = acc.get("token")
        cs_name = acc.get("codespace_name", "cloud-browser-jrwpgvx5r4cqg6p")
        try:
            req = urllib.request.Request(f"https://api.github.com/user/codespaces/{cs_name}/stop", data=b"", method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("User-Agent", "Mozilla/5.0")
            with urllib.request.urlopen(req, timeout=8) as resp:
                return True, f"🛑 Codespace `{cs_name}` successfully shutdown / off kora hoyeche! Monthly free hours save thakbe."
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return True, f"🛑 Codespace `{cs_name}` already shutdown hocche ba bondho ache."
            return False, f"❌ Stop error: {e}"
        except Exception as e:
            return False, f"❌ Stop error: {e}"

    def start_codespace(self) -> Tuple[bool, str]:
        """Start active codespace"""
        import urllib.request, urllib.error
        acc = self.get_active_account()
        if not acc:
            return False, "❌ No active Codespace account configured."
        token = acc.get("token")
        cs_name = acc.get("codespace_name", "cloud-browser-jrwpgvx5r4cqg6p")
        try:
            req = urllib.request.Request(f"https://api.github.com/user/codespaces/{cs_name}/start", data=b"", method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("User-Agent", "Mozilla/5.0")
            with urllib.request.urlopen(req, timeout=8) as resp:
                return True, f"🟢 Codespace `{cs_name}` start kora hoyeche! 15-20s er moddhe ready hobe."
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return True, f"🟢 Codespace `{cs_name}` already starting ba online ache."
            return False, f"❌ Start error: {e}"
        except Exception as e:
            return False, f"❌ Start error: {e}"

    def get_status(self) -> str:
        """Returns comprehensive status of the active codespace & pool"""
        acc = self.get_active_account()
        idx = self.data.get("active_index", 0)
        total = len(self.get_accounts())

        if not acc:
            return "❌ No codespaces configured."

        username = acc.get("username", "Unknown")
        repo = acc.get("repo", "Unknown")
        state = self.get_state()

        if state in ("Shutdown", "ShuttingDown", "Offline"):
            return (
                f"☁️ **CODESPACE STATUS: OFFLINE / SHUTDOWN**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Account:** #{idx + 1} of {total} (`{username}`)\n"
                f"📁 **Repo:** `{repo}`\n"
                f"🛑 **State:** `{state}` (Power OFF)\n"
                f"💡 Free hours bachaner jonno Codespace bondho ache.\n"
                f"Start korte bolun: `codespace on koro` ba `.cloud <cmd>`"
            )

        # Run system check in codespace
        code, out = self.run_command("uname -r && free -h && df -h / | tail -n 1 && uptime -p", timeout=25)
        if code == 0:
            lines = out.splitlines()
            kernel = lines[0] if len(lines) > 0 else "Linux"
            mem = [l for l in lines if "Mem:" in l]
            mem_info = mem[0] if mem else "8 GB RAM Available"
            disk_info = lines[-2] if len(lines) >= 3 else "32 GB Disk Available"
            uptime_str = lines[-1] if len(lines) >= 4 else "Online"

            return (
                f"☁️ **CODESPACE CLOUD WORKER STATUS**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Account:** #{idx + 1} of {total} (`{username}`)\n"
                f"📁 **Repo:** `{repo}`\n"
                f"🟢 **State:** Online & Connected\n"
                f"⏱️ **Uptime:** {uptime_str}\n"
                f"🧠 **Memory:** {mem_info}\n"
                f"💾 **Disk:** {disk_info}\n"
                f"⚡ **Capabilities:** FFmpeg (Video), MoviePy, Python 3.14, Node.js 22"
            )
        else:
            return (
                f"☁️ **CODESPACE STATUS: {state.upper()}**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Account:** #{idx + 1} (`{username}`)\n"
                f"⚠️ Remote worker state: `{state}`\n"
                f"Output: {out}"
            )

cluster_manager = CodespaceClusterManager()
