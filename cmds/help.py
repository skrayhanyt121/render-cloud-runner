from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "help",
    "aliases": ["menu", "cmds", "commands"],
    "category": "General",
    "role": 0,
    "description": "Show interactive command menu and bot capabilities",
    "usage": ".help or .menu"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    is_adm = ctx.is_admin()
    user_role = "👑 Super Admin" if ctx.is_super_admin() else ("⭐ Admin" if is_adm else "👤 User")
    creds = "Unlimited" if is_adm else f"{ctx.get_credits()} Credits"

    menu = (
        "╭────────👑────────╮\n"
        "   AI COMMANDER BOT\n"
        "╰────────👑────────╯\n"
        f"👤 Role: {user_role} | 💳 Balance: {creds}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📧 [GMAIL & LIVE OTP] (Admin/Credit)\n"
        "  • .gmail           : Disposable @gmail.com toiri\n"
        "  • .inbox           : Inbox list & OTP dekha\n"
        "  • 1, 2, 3...       : Number pathalei full mail\n"
        "  • .inbox live      : Auto-alert ON (Instant ping)\n"
        "  • .inbox off       : Alert OFF kora\n\n"
        "📢 [PAGE POST] (Admin/Credit)\n"
        "  • .post <text>     : Page-e direct post kora\n"
        "  • Natural: 'cat image banai post koro'\n\n"
        "☁️ [CLOUD CODESPACE] (Admin/Credit)\n"
        "  • .cloud <cmd>     : 8GB RAM Cloud VM-e run\n"
        "  • .cloudstatus     : VM RAM, CPU & Disk check\n"
        "  • .cloudswitch <1-7>: Burner account change\n\n"
        "👑 [ADMIN & CREDITS]\n"
        "  • .grant <uid> <amt> : User-ke credit deya\n"
        "  • .credits         : Nijer credits check\n"
        "  • .uid             : Facebook UID & role check\n\n"
        "🎰 [GAMES & CREATIVE] (Public)\n"
        "  • .slot            : Casino slot game\n"
        "  • .daily           : 500 free daily coins\n"
        "  • .balance         : Wallet balance\n"
        "  • .img <prompt>    : AI 4K image generate\n"
        "  • .alldl <link>    : Video downloader\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Kono prefix charai direct Banglish-e kotha bolle AI Agent nijei shob kaj kore dibe!"
    )
    return menu, None
