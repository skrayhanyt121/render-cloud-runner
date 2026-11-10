from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "kick",
    "aliases": ["remove"],
    "category": "Group Moderation",
    "role": 1,
    "description": "Kick or remove a member from the group chat",
    "usage": ".kick @mention or reply to member's message with .kick"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    if not ctx.is_group:
        return "⚠️ Ei command-ti shudhu Messenger Group Chat-e kaj korbe!", None

    target = ctx.args.strip()
    if not target:
        return (
            "╭────── 🚫 𝐊𝐈𝐂𝐊 𝐌𝐄𝐌𝐁𝐄𝐑 ──────╮\n"
            "Group theke member kick korte:\n"
            "1. .kick @mention (tag korun)\n"
            "2. Ba oi member-er message-e reply kore .kick likhun!\n"
            "╰─────────────────────────────╯"
        ), None

    # On Facebook Graph API Page / Messenger GC:
    # Requires thread admin rights or Graph API /chat thread endpoints
    return f"🛡️ Kick request received for {target} by Admin {ctx.sender_name}!", None
