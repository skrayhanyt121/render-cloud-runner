import logging
from typing import Tuple, Optional
from .context import CommandContext

logger = logging.getLogger("CmdAdmin")

config = {
    "name": "admin",
    "aliases": ["grant", "givecredit", "setcredit", "credits", "mycredits", "addadmin", "removeadmin", "adminlist", "creditlist"],
    "version": "1.0.0",
    "description": "Manage user credits, grant permissions, and list admins",
    "usage": ".grant <uid> <credits> | .credits | .addadmin <uid> | .adminlist",
    "admin_only": False,
    "group_enabled": True
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    cmd = (ctx.cmd_name or "").lower()
    args = ctx.args.strip().split()

    # ─────────────────────────────────────────────────────────────
    # PUBLIC ACTION: CHECK MY CREDITS / CHECK USER CREDITS
    # ─────────────────────────────────────────────────────────────
    if cmd in ("credits", "mycredits"):
        target_uid = args[0] if args and args[0].isdigit() else ctx.sender_id
        is_adm = ctx.db.is_admin(target_uid)
        creds = "Unlimited (Admin)" if is_adm else f"{ctx.db.get_credits(target_uid)} Credits"
        role = "👑 Super Admin" if ctx.db.is_super_admin(target_uid) else ("⭐ Admin" if is_adm else "👤 Regular User")

        return (
            f"💳 **CREDIT BALANCE**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 **UID:** `{target_uid}`\n"
            f"🏷️ **Role:** {role}\n"
            f"💰 **Balance:** {creds}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Admin-only command (e.g. .gmail, .post) run korle 1 credit kete neya hoy.",
            None
        )

    # ─────────────────────────────────────────────────────────────
    # ADMIN ACTION: LIST ALL ADMINS
    # ─────────────────────────────────────────────────────────────
    if cmd == "adminlist":
        admins = ctx.db.get_all_admins()
        lines = []
        for i, a in enumerate(admins, 1):
            lines.append(f"{i}. {a.get('role', 'Admin')}: `{a.get('user_id')}` ({a.get('name', 'Admin')})")
        return (
            f"👑 **BOT ADMIN LIST**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines) +
            "\n━━━━━━━━━━━━━━━━━━━\n"
            "Main Admin: `61595863212209`",
            None
        )

    # ─────────────────────────────────────────────────────────────
    # ADMIN ACTION: LIST USERS WITH CREDITS
    # ─────────────────────────────────────────────────────────────
    if cmd == "creditlist":
        if not ctx.is_admin():
            return "⛔ Shudhu Admin ei list dekhte parbe.", None
        users = ctx.db.get_users_with_credits()
        if not users:
            return "ℹ️ Ekhono kono user-ke credit deya hoyni.", None
        lines = [f"{i}. UID: `{u['user_id']}` ➔ 💳 {u['credits']} Credits" for i, u in enumerate(users[:15], 1)]
        return (
            f"📋 **ACTIVE CREDIT USERS**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(lines),
            None
        )

    # ─────────────────────────────────────────────────────────────
    # ADMIN ACTION: GRANT / ADD CREDITS TO A UID
    # ─────────────────────────────────────────────────────────────
    if cmd in ("grant", "givecredit"):
        if not ctx.is_admin():
            return "⛔ Shudhu Admin onno user-ke credit grant korte pare.", None
        if len(args) < 2 or not args[1].isdigit():
            return "⚠️ Usage: `.grant <uid> <amount>` (e.g. `.grant 29150849791232816 10`)", None

        target_uid = args[0].strip()
        amount = int(args[1])
        new_total = ctx.db.add_credits(target_uid, amount)

        return (
            f"✅ **CREDIT GRANTED SUCCESSFULLY!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Target UID:** `{target_uid}`\n"
            f"➕ **Added:** +{amount} Credits\n"
            f"💰 **Total Balance:** {new_total} Credits\n\n"
            f"Ekhon ei user bot-er Admin-only commands ({amount} bar) use korte parbe!",
            None
        )

    # ─────────────────────────────────────────────────────────────
    # ADMIN ACTION: SET EXACT CREDITS
    # ─────────────────────────────────────────────────────────────
    if cmd == "setcredit":
        if not ctx.is_admin():
            return "⛔ Shudhu Admin credit set korte pare.", None
        if len(args) < 2 or not args[1].isdigit():
            return "⚠️ Usage: `.setcredit <uid> <amount>` (e.g. `.setcredit 29150849791232816 5`)", None

        target_uid = args[0].strip()
        amount = int(args[1])
        new_total = ctx.db.set_credits(target_uid, amount)

        return (
            f"✅ **CREDIT UPDATED!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Target UID:** `{target_uid}`\n"
            f"💰 **New Balance:** {new_total} Credits",
            None
        )

    # ─────────────────────────────────────────────────────────────
    # SUPER ADMIN ACTION: ADD SUB-ADMIN
    # ─────────────────────────────────────────────────────────────
    if cmd == "addadmin":
        if not ctx.is_super_admin():
            return "⛔ Shudhu Main Admin (`61595863212209`) notun Admin add korte pare.", None
        if not args or not args[0].isdigit():
            return "⚠️ Usage: `.addadmin <uid> [name]` (e.g. `.addadmin 122101774221540465 Sifat`)", None

        target_uid = args[0]
        name = " ".join(args[1:]) if len(args) > 1 else "Sub-Admin"
        ctx.db.add_admin(target_uid, name, added_by=ctx.sender_id)

        return (
            f"👑 **NEW ADMIN ADDED!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Admin UID:** `{target_uid}`\n"
            f"📛 **Name:** {name}\n"
            f"⚡ **Status:** Unlimited Access to all bot commands!",
            None
        )

    # ─────────────────────────────────────────────────────────────
    # SUPER ADMIN ACTION: REMOVE SUB-ADMIN
    # ─────────────────────────────────────────────────────────────
    if cmd == "removeadmin":
        if not ctx.is_super_admin():
            return "⛔ Shudhu Main Admin (`61595863212209`) Admin remove korte pare.", None
        if not args or not args[0].isdigit():
            return "⚠️ Usage: `.removeadmin <uid>`", None

        target_uid = args[0]
        success = ctx.db.remove_admin(target_uid)
        if success:
            return f"✅ Admin `{target_uid}` ke shofolbhabe remove kora hoyeche.", None
        else:
            return f"❌ Admin `{target_uid}` remove kora jayni (eita Super Admin ba pawa jayni).", None

    return (
        "👑 **Admin & Credit Management Menu**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "• `.grant <uid> <amount>` : User-ke credit deya\n"
        "• `.setcredit <uid> <amt>` : Exact credit set kora\n"
        "• `.credits [uid]` : Nijer ba onner credit check\n"
        "• `.creditlist` : Credit pawa shob user-er list\n"
        "• `.addadmin <uid>` : Notun admin add kora (Super Admin)\n"
        "• `.adminlist` : Shob admin-er list dekha",
        None
    )
