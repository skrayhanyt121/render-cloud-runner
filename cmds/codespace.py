import logging
from typing import Tuple, Optional
from codespace_cluster import cluster_manager
from .context import CommandContext

logger = logging.getLogger("CmdCodespace")

config = {
    "name": "cloud",
    "aliases": ["cs", "codespace", "cloudstatus", "cloudswitch", "vm"],
    "version": "1.0.0",
    "description": "Execute bash commands or check status on 8GB RAM Codespace Cloud VM",
    "usage": ".cloud <bash command> | .cloudstatus | .cloudswitch <1-7>",
    "admin_only": True,
    "group_enabled": True
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    raw_cmd = ctx.raw_text.strip()
    cmd_lower = raw_cmd.lower()

    if cmd_lower.startswith(".cloudswitch") or cmd_lower.startswith("/cloudswitch"):
        args = ctx.args.strip()
        if not args or not args.isdigit():
            return "⚠️ Usage: `.cloudswitch <1-7>` (e.g. `.cloudswitch 2`)", None
        target_idx = int(args) - 1
        success, msg = cluster_manager.switch_account(target_idx)
        return msg, None

    if cmd_lower in (".cloudstatus", "/cloudstatus", ".cloud", "/cloud") and not ctx.args:
        status_report = cluster_manager.get_status()
        return status_report, None

    # Run bash command remotely in the Codespace
    command_to_run = ctx.args.strip()
    if not command_to_run:
        return (
            "☁️ **Codespace Cloud Runner Help**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "• `.cloud <cmd>` : Run any shell command in 8GB RAM Cloud VM\n"
            "• `.cloudstatus` : Show active account, RAM, CPU & disk\n"
            "• `.cloudswitch <1-7>` : Switch between the 7 burner accounts\n\n"
            "Example: `.cloud python3 -c 'print(2**100)'`",
            None
        )

    code, output = cluster_manager.run_command(command_to_run, timeout=45)
    header = "🟢 **Execution Result**" if code == 0 else f"⚠️ **Exit Code: {code}**"

    # Messenger message length safety limit
    if len(output) > 1800:
        output = output[:1800] + "\n... [Output truncated]"

    return f"{header}\n━━━━━━━━━━━━━━━━━━━\n```\n{output}\n```", None
