import os
import sys
import importlib.util
import logging
from typing import Dict, Any, Tuple, Optional

from .context import CommandContext, db
from cybervault_gateway_client import gateway_client
from autonomous_agent import AutonomousAIAgent

logger = logging.getLogger("CommandLoader")

# Commands that are safe to trigger as standalone single words without dot prefix
STANDALONE_NO_PREFIX_CMDS = {"help", "menu", "slot", "daily", "balance", "top", "inbox", "gmail", "gamil", "uid", "credits"}

class CommandLoader:
    def __init__(self, fb_api):
        self.fb = fb_api
        self.ai_agent = AutonomousAIAgent(self.fb)
        self.commands: Dict[str, Any] = {}
        self.aliases: Dict[str, str] = {}
        self.modules: Dict[str, Any] = {}
        self.load_all()

    def load_all(self):
        cmds_dir = os.path.dirname(__file__)
        self.commands.clear()
        self.aliases.clear()
        self.modules.clear()

        for filename in os.listdir(cmds_dir):
            if filename.endswith(".py") and filename not in ("__init__.py", "loader.py", "context.py"):
                mod_name = filename[:-3]
                file_path = os.path.join(cmds_dir, filename)
                try:
                    spec = importlib.util.spec_from_file_location(f"cmds.{mod_name}", file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[f"cmds.{mod_name}"] = module
                        spec.loader.exec_module(module)

                        if hasattr(module, "config") and hasattr(module, "on_execute"):
                            cfg = module.config
                            primary_name = cfg.get("name", mod_name).lower()
                            self.commands[primary_name] = module
                            self.modules[primary_name] = cfg

                            for alias in cfg.get("aliases", []):
                                self.aliases[alias.lower()] = primary_name
                            
                            logger.info(f"Loaded command: .{primary_name} (aliases: {cfg.get('aliases', [])})")
                except Exception as e:
                    logger.error(f"Failed to load command {filename}: {e}")

        logger.info(f"Successfully loaded {len(self.commands)} modular commands!")

    def dispatch(self, text: str, sender_id: str, sender_name: str, is_group: bool = False, thread_id: str = "", video_url: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        text_clean = text.strip()
        if not text_clean:
            return None, None

        cmd_name = ""
        target_name = ""
        args = ""

        # 1. Quick digit check: If user typed '1', '2', etc. after viewing inbox
        if text_clean.isdigit():
            cached_ids = db.get_cached_msg_ids(sender_id)
            if cached_ids:
                cmd_name = "readmail"
                target_name = "gmail"
                args = text_clean

        # 2. Explicit prefix commands (.cmd, /cmd, . cmd)
        has_prefix = text_clean.startswith(".") or text_clean.startswith("/")
        if not target_name and has_prefix:
            cleaned = text_clean.lstrip("./").strip()
            parts = cleaned.split(maxsplit=1)
            candidate = parts[0].lower() if parts else ""
            if candidate in self.commands or candidate in self.aliases:
                cmd_name = candidate
                target_name = self.aliases.get(cmd_name, cmd_name)
                args = parts[1].strip() if len(parts) > 1 else ""

        # 3. Standalone 1-word commands without prefix (e.g. "help", "menu", "slot")
        if not target_name and not has_prefix:
            words = text_clean.split()
            if len(words) == 1:
                single = words[0].lower()
                if single in STANDALONE_NO_PREFIX_CMDS and (single in self.commands or single in self.aliases):
                    cmd_name = single
                    target_name = self.aliases.get(cmd_name, cmd_name)
                    args = ""

        # 4. Execute registered direct command if matched
        if target_name in self.commands:
            mod = self.commands[target_name]
            cfg = self.modules.get(target_name, {})
            is_admin_only = cfg.get("admin_only", False)

            ctx = CommandContext(
                sender_id=sender_id,
                sender_name=sender_name,
                raw_text=text_clean,
                args=args,
                is_group=is_group,
                thread_id=thread_id or sender_id,
                fb_api=self.fb,
                cmd_name=cmd_name
            )

            # Enforce Admin & Credit System
            credit_notice = ""
            if is_admin_only:
                if ctx.is_admin():
                    pass  # Admins have unlimited access
                else:
                    # Check and deduct 1 credit for regular users
                    allowed, remaining = ctx.deduct_credit(cost=1)
                    if not allowed:
                        return (
                            "⛔ **ACCESS RESTRICTED! (Admin & Credit Only)**\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            "Ei command-ti shudhu Admin ebong Access prapto user-ra use korte pare.\n"
                            "Apnar kache kono credit nei (Credits: 0).\n\n"
                            "👑 Access ba Credit pete Main Admin-er shathe jogajog korun:\n"
                            "🆔 **Main Admin UID:** `61595863212209`\n"
                            f"📌 **Apnar UID:** `{sender_id}`\n\n"
                            "💡 Admin apnar UID-te credit dile apni command use korte parben!",
                            None
                        )
                    else:
                        credit_notice = f"\n\n💳 *[1 Credit kete neya hoyeche | Baki credit: {remaining}]*"

            try:
                reply, img = mod.on_execute(ctx)
                if reply and credit_notice:
                    reply += credit_notice
                return reply, img
            except Exception as e:
                logger.error(f"Error executing command .{target_name}: {e}")
                return f"❌ Command .{target_name} execution error: {e}", None

        # 5. Autonomous AI Agent (Natural Language Reasoning, Cloud Codespaces, Posts & Tools Control)
        return self.ai_agent.process_message(text_clean, sender_id, sender_name, video_url=video_url)
