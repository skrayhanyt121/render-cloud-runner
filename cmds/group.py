from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "group",
    "aliases": ["all", "adduser", "botnick", "gc"],
    "category": "Group Moderation",
    "role": 1,
    "description": "Tag everyone, add users, change bot nickname in group",
    "usage": ".all [text] or .adduser <uid/link>"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    raw = ctx.raw_text.lower()
    if raw.startswith(".all") or raw.startswith("/all"):
        tag_text = ctx.args or "Shobai ekbar inbox-e asho! 📢"
        return (
            f"📣 𝐀𝐓𝐓𝐄𝐍𝐓𝐈𝐎𝐍 𝐄𝐕𝐄𝐑𝐘𝐎𝐍𝐄! 📣\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Tagged by: {ctx.sender_name}\n"
            f"💬 Message: {tag_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 @everyone @here"
        ), None

    elif raw.startswith(".adduser") or raw.startswith("/adduser"):
        if not ctx.args:
            return "📌 Member add korte Facebook Link ba Numeric UID din:\nExample: .adduser 100082736452", None
        return f"➕ Member add request queued for: {ctx.args}", None

    elif raw.startswith(".botnick") or raw.startswith("/botnick"):
        nick = ctx.args or "AI Commander 🤖"
        return f"✨ Bot nickname changed to: {nick}", None

    return (
        f"👥 Group Tools Available:\n"
        f"- .all [message] : Tag all members\n"
        f"- .kick @user : Remove user from group\n"
        f"- .adduser <link/uid> : Add user to group\n"
        f"- .botnick <name> : Change bot name"
    ), None
