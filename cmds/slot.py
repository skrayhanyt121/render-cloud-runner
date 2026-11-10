import random
from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "slot",
    "aliases": ["spin", "gamble"],
    "category": "Economy & Games",
    "role": 0,
    "description": "3-reel casino slot game to win coins",
    "usage": ".slot"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    user = ctx.db.get_user(ctx.sender_id, ctx.sender_name)
    balance = user["balance"]

    bet_amount = 50
    if balance < bet_amount:
        return f"❌ {ctx.sender_name}, apnar balance kom! Daily bonus claim korte likhun: .daily", None

    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣", "🔔"]
    s1 = random.choice(symbols)
    s2 = random.choice(symbols)
    s3 = random.choice(symbols)

    if s1 == s2 == s3:
        win = 500
        new_bal = ctx.db.update_balance(ctx.sender_id, win)
        result_text = f"🎉 JACKPOT! Apni {win} coins jitechen!"
    elif s1 == s2 or s2 == s3 or s1 == s3:
        win = 100
        new_bal = ctx.db.update_balance(ctx.sender_id, win)
        result_text = f"✨ 2-ta mileche! Apni {win} coins jitechen!"
    else:
        new_bal = ctx.db.update_balance(ctx.sender_id, -bet_amount)
        result_text = f"😢 Meleni! {bet_amount} coins kata gelo."

    msg = (
        f"🎰 𝐒𝐋𝐎𝐓 𝐌𝐀𝐂𝐇𝐈𝐍𝐄 🎰\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"   [ {s1} | {s2} | {s3} ]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{result_text}\n"
        f"💰 Current Balance: {new_bal} coins"
    )
    return msg, None
