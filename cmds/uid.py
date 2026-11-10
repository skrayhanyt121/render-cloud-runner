import re
import urllib.request
import urllib.parse
import logging
from typing import Tuple, Optional
from .context import CommandContext

logger = logging.getLogger("CmdUID")

config = {
    "name": "uid",
    "aliases": ["myid", "id", "getid"],
    "version": "1.0.0",
    "description": "Get your Facebook User ID (UID) or resolve UID from profile link",
    "usage": ".uid | .uid <facebook_profile_url>",
    "admin_only": False,
    "group_enabled": True
}

def resolve_uid_from_url(url: str) -> Optional[str]:
    """Resolves Facebook Profile URL to numeric UID"""
    clean_url = url.strip()
    
    # 1. Direct regex check if already contains numeric ID in URL
    match = re.search(r'(?:id=|\/user\/|\/profile\.php\?id=)(\d+)', clean_url)
    if match:
        return match.group(1)

    # 2. Try SEO Magnifier API
    try:
        data = urllib.parse.urlencode({"facebook": "1", "sitelink": clean_url}).encode()
        req = urllib.request.Request(
            "https://seomagnifier.com/fbid",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            text = resp.read().decode().strip()
            if text.isdigit() and len(text) > 4:
                return text
    except Exception as e:
        logger.debug(f"Seomagnifier lookup failed: {e}")

    # 3. Direct HTML Meta scraper
    try:
        req = urllib.request.Request(
            clean_url,
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode(errors="ignore")
            # Look for android app link: fb://profile/<id>
            m = re.search(r'fb://profile/(\d+)', html) or re.search(r'al:android:url.*profile/(\d+)', html) or re.search(r'"entity_id":"(\d+)"', html)
            if m:
                return m.group(1)
    except Exception as e:
        logger.debug(f"HTML scraper failed: {e}")

    return None

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    args = ctx.args.strip()

    # Case 1: Resolve UID from Profile URL
    if args and ("facebook.com" in args or "fb.me" in args or "fb.com" in args):
        resolved = resolve_uid_from_url(args)
        if resolved:
            role = "👑 Super Admin" if ctx.db.is_super_admin(resolved) else ("⭐ Admin" if ctx.db.is_admin(resolved) else "👤 User")
            creds = "Unlimited" if ctx.db.is_admin(resolved) else f"{ctx.db.get_credits(resolved)} Credits"
            return (
                f"🆔 **FACEBOOK UID DETECTED!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 **URL:** {args}\n"
                f"🔢 **UID:** `{resolved}`\n"
                f"🏷️ **Role:** {role}\n"
                f"💳 **Credits:** {creds}",
                None
            )
        else:
            return f"❌ Profile link theke UID ber kora jayni: {args}", None

    # Case 2: Query another UID
    if args and args.isdigit():
        target_uid = args
        role = "👑 Super Admin" if ctx.db.is_super_admin(target_uid) else ("⭐ Admin" if ctx.db.is_admin(target_uid) else "👤 User")
        creds = "Unlimited" if ctx.db.is_admin(target_uid) else f"{ctx.db.get_credits(target_uid)} Credits"
        return (
            f"🆔 **USER UID INFO**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 **UID:** `{target_uid}`\n"
            f"🏷️ **Role:** {role}\n"
            f"💳 **Credits:** {creds}",
            None
        )

    # Case 3: Show sender's own UID
    role = "👑 Super Admin" if ctx.is_super_admin() else ("⭐ Admin" if ctx.is_admin() else "👤 Regular User")
    creds = "Unlimited" if ctx.is_admin() else f"{ctx.get_credits()} Credits"

    return (
        f"🆔 **YOUR FACEBOOK UID**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Name:** {ctx.sender_name}\n"
        f"🔢 **UID:** `{ctx.sender_id}`\n"
        f"🏷️ **Role:** {role}\n"
        f"💳 **Credits:** {creds}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Kono profile link er UID ber korte likhun: `.uid <link>`",
        None
    )
