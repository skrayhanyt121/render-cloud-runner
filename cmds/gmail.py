import logging
from typing import Tuple, Optional, List
from tempgmail import TempGmailClient
from .context import CommandContext

logger = logging.getLogger("CmdGmail")
mail_client = TempGmailClient()

config = {
    "name": "gmail",
    "aliases": ["gamil", "tempmail", "mail", "inbox", "checkmail", "readmail", "read"],
    "version": "2.0.0",
    "description": "Real disposable @gmail.com generator, auto OTP extractor & live notification engine",
    "usage": ".gmail | .inbox [live/on/off] | .readmail <num/id> | reply with '1' or '2'",
    "admin_only": True,
    "group_enabled": True
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    cmd = (ctx.cmd_name or "").lower()
    args_raw = ctx.args.strip()
    args_lower = args_raw.lower()

    # ─────────────────────────────────────────────────────────────
    # ACTION 1: READ EMAIL FULL BODY (.readmail <num/id> or '1', '2')
    # ─────────────────────────────────────────────────────────────
    if cmd in ("readmail", "read"):
        if not args_raw:
            return "⚠️ Usage: `.readmail <number>` (e.g. `.readmail 1` ba shudhu `1`)", None

        msg_id = args_raw
        # Check if argument is a list index (1, 2, 3...)
        if args_raw.isdigit():
            idx = int(args_raw)
            cached_ids = ctx.db.get_cached_msg_ids(ctx.sender_id)
            if not cached_ids:
                return "⚠️ Kono email list pawa jayni! Age `.inbox` likhe list check korun.", None
            if 1 <= idx <= len(cached_ids):
                msg_id = cached_ids[idx - 1]
            else:
                return f"⚠️ Invalid number! List-e matro {len(cached_ids)}-ti email ache. 1 theke {len(cached_ids)} er moddhe number din.", None

        try:
            msg = mail_client.get_message(msg_id)
            sender = msg.get("sender", "Unknown")
            subject = msg.get("subject", "No Subject")
            otp = msg.get("extracted_otp") or mail_client.extract_otp(subject, msg.get("body_plain", ""))
            body = msg.get("body_plain", "").strip() or "No plain text content."

            if len(body) > 1400:
                body = body[:1400] + "\n\n... [Content truncated for length]"

            otp_badge = f"🔥 **OTP / VERIFICATION CODE:** `{otp}`\n━━━━━━━━━━━━━━━━━━━\n" if otp else ""

            report = (
                f"📨 **EMAIL DETAILS**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **From:** {sender}\n"
                f"📌 **Subject:** {subject}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{otp_badge}"
                f"📄 **Message Content:**\n"
                f"```\n{body}\n```"
            )
            return report, None
        except Exception as e:
            logger.error(f"Error reading message {msg_id}: {e}")
            return f"❌ Email fetch korte shomoshya: {e}", None

    # ─────────────────────────────────────────────────────────────
    # ACTION 2: INBOX CHECK & LIVE NOTIFICATION (.inbox [live/on/off])
    # ─────────────────────────────────────────────────────────────
    if cmd in ("inbox", "checkmail"):
        target_email = ctx.db.get_user_email(ctx.sender_id)

        # Sub-mode: Live notification toggle ON / LIVE
        if args_lower in ("live", "on", "start"):
            if not target_email:
                return "⚠️ Apnar kono active Temp Gmail nei! Age `.gmail` likhe ekta email create korun.", None
            ctx.db.set_live_notify(ctx.sender_id, 1)
            return (
                f"🔔 **LIVE INBOX NOTIFICATION ACTIVATED!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📬 **Monitoring Gmail:** `{target_email}`\n"
                f"🟢 **Status:** Active (Every 6s Background Monitor)\n\n"
                f"Ei Gmail-e kono notun email (GitHub, Netflix, Instagram, etc.) ashar shathe shathe bot apnake Messenger-e alert o OTP pathiye dibe!\n\n"
                f"🔕 Notification bondho korte: `.inbox off`",
                None
            )

        # Sub-mode: Live notification toggle OFF
        if args_lower in ("off", "stop"):
            ctx.db.set_live_notify(ctx.sender_id, 0)
            return (
                f"🔕 **LIVE INBOX NOTIFICATION DEACTIVATED!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📬 **Gmail:** `{target_email or 'None'}`\n"
                f"⚪ **Status:** Live Monitoring Stopped\n\n"
                f"Ekhon theke background alert asbe na. Chaili manual `.inbox` likhe check korte parben.",
                None
            )

        # Regular manual inbox check
        if args_raw and "@" in args_raw:
            target_email = args_raw

        if not target_email:
            return (
                "⚠️ Apnar kono active Temp Gmail nei!\n"
                "👉 Age `.gmail` likhe ekta real @gmail.com address generate korun, tarpor `.inbox` din.",
                None
            )

        try:
            inbox_data = mail_client.get_inbox(target_email)
            messages = inbox_data.get("messages", [])
            count = len(messages)

            if count == 0:
                return (
                    f"📬 **INBOX: `{target_email}`**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"ℹ️ Inbox-e ekhono kono email asheni!\n"
                    f"Website theke code pathanor por 5-10 second opekkha kore abar `.inbox` likhun.\n\n"
                    f"🔔 Automatic alert pete chaile: `.inbox live` likhun!",
                    None
                )

            # Cache the latest up-to 10 message IDs for quick numeric selection ('1', '2'...)
            cached_ids: List[str] = []
            msg_list = []
            for i, m in enumerate(messages[:8], 1):
                mid = m.get("id", "")
                cached_ids.append(mid)
                sender = m.get("sender", "Unknown")
                # Clean up sender display
                sender_clean = sender.split("<")[0].strip().replace('"', '') or sender
                subj = m.get("subject", "No Subject")
                body = m.get("body_plain", "")

                otp = mail_client.extract_otp(subj, body)
                otp_badge = f"\n   🔥 **OTP / CODE:** `{otp}`" if otp else ""

                msg_list.append(
                    f"{i}. 📩 **{sender_clean}**\n"
                    f"   📌 Subject: {subj}{otp_badge}\n"
                    f"   👉 Porte: `{i}` pathan"
                )

            ctx.db.set_cached_msg_ids(ctx.sender_id, cached_ids)
            items_str = "\n\n".join(msg_list)

            return (
                f"📬 **INBOX: `{target_email}`** (Total: {count})\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{items_str}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💡 Je kono email pura porte shudhu tar number pathan (e.g. `1` ba `2`)!\n"
                f"🔔 Live instant alert pete: `.inbox live`",
                None
            )
        except Exception as e:
            logger.error(f"Error checking inbox for {target_email}: {e}")
            return f"❌ Inbox check korte shomoshya: {e}", None

    # ─────────────────────────────────────────────────────────────
    # ACTION 3: GENERATE FRESH REAL GMAIL (.gmail / .tempmail / .mail)
    # ─────────────────────────────────────────────────────────────
    try:
        data = mail_client.get_random_email()
        email = data.get("email")
        existing_msgs = data.get("messages", [])
        existing_ids = [m.get("id") for m in existing_msgs if m.get("id")]

        # Save to database and record existing IDs so only NEW emails notify user
        ctx.db.set_user_email(ctx.sender_id, email, initial_msg_ids=existing_ids)

        return (
            f"📧 **REAL TEMP GMAIL GENERATED!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📬 **Your Gmail Address:**\n"
            f"`{email}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 **Kivabe use korben:**\n"
            f"1. Ei Gmail copy kore GitHub, Netflix, Instagram ba password reset-e boshan.\n"
            f"2. Email ashar sathe sathe auto-notification pete likhun: **`.inbox live`**\n"
            f"3. Manual check korte likhun: **`.inbox`**\n"
            f"4. Ashar por shudhu **`1`** pathalei full email dekhte paben!\n\n"
            f"🔄 Notun email lagle abar `.gmail` likhun.",
            None
        )
    except Exception as e:
        logger.error(f"Error generating random temp gmail: {e}")
        return f"❌ Gmail generate korte shomoshya hoyeche: {e}", None
