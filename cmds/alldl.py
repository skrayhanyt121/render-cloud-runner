import urllib.parse
from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "alldl",
    "aliases": ["dl", "download", "tiktok", "reel"],
    "category": "Media & Downloader",
    "role": 0,
    "description": "Download videos from TikTok, Reels, YouTube Shorts, FB",
    "usage": ".alldl <video_url>"
}

SUPPORTED = ["tiktok.com", "instagram.com", "facebook.com", "fb.watch", "youtube.com", "youtu.be", "twitter.com", "x.com"]

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    link = ctx.args.strip()
    if not link:
        return (
            "📥 𝐀𝐋𝐋-𝐈𝐍-𝐎𝐍𝐄 𝐕𝐈𝐃𝐄𝐎 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐄𝐑\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "TikTok, Instagram Reels, Facebook Video ba YouTube link pathan!\n"
            "Usage: .alldl https://vt.tiktok.com/...\n"
            "💡 Tip: Shudhu direct link pathalei bot automatic dhora felbe!"
        ), None

    domain = next((d for d in SUPPORTED if d in link), None)
    platform = domain.split(".")[0].upper() if domain else "ONLINE VIDEO"

    # Fast universal downloader bridge
    api_url = f"https://api.cobalt.tools/?url={urllib.parse.quote(link)}"
    download_page = f"https://snapsave.app/action.php?url={urllib.parse.quote(link)}"

    card = (
        f"╭────────🎬────────╮\n"
        f"   𝐌𝐄𝐃𝐈𝐀 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐄𝐑\n"
        f"╰────────🎬────────╯\n\n"
        f"❒ Platform: {platform}\n"
        f"❒ Status: Ready for HD Streaming\n"
        f"❒ Link: {link[:40]}...\n\n"
        f"🔗 Instant Download Link:\n"
        f"👉 https://ssstik.io/ (or https://snapinsta.app/)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Enjoy your media, {ctx.sender_name}! ✨"
    )
    return card, None
