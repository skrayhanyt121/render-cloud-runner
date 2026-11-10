import time
from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "economy",
    "aliases": ["balance", "bal", "daily", "top", "leaderboard", "bank"],
    "category": "Economy & Games",
    "role": 0,
    "description": "Virtual bank, coin balances, daily rewards, leaderboard",
    "usage": ".balance or .daily or .top"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    raw = ctx.raw_text.lower()
    user = ctx.db.get_user(ctx.sender_id, ctx.sender_name)

    if raw.startswith(".daily") or raw.startswith("/daily") or raw == "daily":
        now = int(time.time())
        last = user["last_daily"]
        # 24 hour cooldown (86400s)
        if now - last < 86400:
            remaining_hrs = int((86400 - (now - last)) / 3600)
            remaining_mins = int(((86400 - (now - last)) % 3600) / 60)
            return f"⏳ {ctx.sender_name}, apni already ajker daily bonus claim korechen! Abar {remaining_hrs} ghonta {remaining_mins} minute por claim korte parben।", None

        new_bal = ctx.db.set_daily(ctx.sender_id, now, bonus=500)
        return (
            f"🎁 𝐃𝐀𝐈𝐋𝐘 𝐑𝐄𝐖𝐀𝐑𝐃! 🎁\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Bonus: +500 coins!\n"
            f"🏦 Current Balance: {new_bal} coins\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎰 Khela shuru korte likhun: .slot"
        ), None

    elif raw.startswith(".top") or raw.startswith("/top") or raw == "top":
        top_users = ctx.db.get_top_users(limit=5)
        lines = [f"{i+1}. 👤 {u[0]}: 💰 {u[1]} coins" for i, u in enumerate(top_users)]
        return (
            f"🏆 𝐑𝐈𝐂𝐇𝐄𝐒𝐓 𝐏𝐋𝐀𝐘𝐄𝐑𝐒 🏆\n"
            f"━━━━━━━━━━━━━━━━━━━━\n" +
            "\n".join(lines) +
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Daily coins claim korte: .daily"
        ), None

    else:
        # Balance check
        bal = user["balance"]
        return (
            f"💳 𝐔𝐒𝐄𝐑 𝐖𝐀𝐋𝐋𝐄𝐓 💳\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Account: {ctx.sender_name}\n"
            f"💰 Balance / Coins: {bal} coins\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎰 Casino khelar jonno: .slot\n"
            f"🎁 Daily free coins: .daily"
        ), None
