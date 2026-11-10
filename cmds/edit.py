import os
import time
import json
import logging
import urllib.request
import urllib.parse
from typing import Tuple, Optional
from .context import CommandContext
from video_engine import VideoEngine

logger = logging.getLogger("CmdEdit")

config = {
    "name": "edit",
    "aliases": ["imageedit", "ai-edit", "imgedit", "editor"],
    "category": "AI & Image Generation",
    "role": 0,
    "description": "AI Image Editor - Edit any photo with text prompts (Anime, Cyberpunk, Background, etc.)",
    "usage": ".edit <prompt> (reply to an image, send after photo, or paste image link)"
}

def edit_image_via_api(image_url: str, prompt: str) -> Optional[str]:
    """Call azadx69x image editor API and save result locally with rate-limit retry."""
    api_url = f"https://azadx69x.is-a.dev/api/editor?url={urllib.parse.quote(image_url)}&prompt={urllib.parse.quote(prompt)}"
    for attempt in range(2):
        try:
            req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = resp.read()
                if data.startswith(b"{") and b"error" in data:
                    logger.warning(f"Editor API returned JSON error (attempt {attempt+1}): {data[:200]}")
                    if b"429" in data and attempt == 0:
                        time.sleep(3.5)
                        continue
                    return None
                out_path = f"/tmp/edited_image_{int(time.time())}.png"
                with open(out_path, "wb") as f:
                    f.write(data)
                return out_path
        except Exception as e:
            logger.error(f"Error calling editor API (attempt {attempt+1}): {e}")
            if attempt == 0:
                time.sleep(2.5)
                continue
            return None
    return None

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    args = ctx.args.strip()
    
    # 1. Look for image URL in args or user's persisted media
    image_url = None
    prompt = args

    # Check if a URL was passed inside args
    words = args.split()
    for w in words:
        if w.startswith("http://") or w.startswith("https://"):
            image_url = w
            prompt = args.replace(w, "").strip()
            break

    # If no URL in args, check user's persisted last media
    if not image_url:
        media = ctx.db.get_last_media(ctx.sender_id)
        image_url = media.get("image_url")

    if not image_url:
        return (
            "⚠️ **Kono Photo ba Image Paini!**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Age Messenger-e ekta photo/image pathan ba image-er link din!\n"
            "Tarpor bolun `.edit <prompt>`.\n\n"
            "💡 **Examples:**\n"
            "• `.edit make it anime style`\n"
            "• `.edit change background to space`\n"
            "• `.edit cyberpunk neon glow`"
        ), None

    if not prompt:
        prompt = "enhance and make it aesthetic anime artwork"

    # Call AI Image Editor
    local_img = edit_image_via_api(image_url, prompt)
    if not local_img or not os.path.exists(local_img):
        return (
            "❌ **Image Edit Korte Shomoshya Hoyeche!**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "API theke image generate kora jayni. Onno kono prompt ba image diye abar cheshta korun."
        ), None

    # Try uploading to Catbox for ultra-fast CDN delivery, fallback to local file
    catbox_url = VideoEngine.upload_to_catbox(local_img)
    media_target = catbox_url if catbox_url else f"image_file:{local_img}"

    caption = (
        f"✨ **Image Edited Successfully!** 🎨\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📝 **Prompt:** {prompt}\n"
        f"👤 **User:** {ctx.sender_name}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Notun edit korte abar photo pathan ba `.edit <prompt>` likhun!"
    )
    return caption, media_target
