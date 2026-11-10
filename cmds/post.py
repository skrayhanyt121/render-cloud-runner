import re
import urllib.parse
import random
from typing import Tuple, Optional
from .context import CommandContext
from gemini_keys_client import gemini_manager

config = {
    "name": "post",
    "aliases": ["publish", "postfb"],
    "category": "Admin & Publishing",
    "role": 2,
    "admin_only": True,
    "description": "Publish direct post to Facebook Page, or tell AI to generate an image and post",
    "usage": ".post <raw text> OR say in chat 'post koro cat image banaye cat er bepare'"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    raw = ctx.raw_text.strip()

    # Rule: If starts with '.post', execute raw post directly without AI conversational reply
    if raw.startswith(".post") or raw.startswith("/post"):
        post_text = ctx.args.strip()
        if not post_text:
            return "📢 Page-e post korte text din:\nExample: .post Shobai kemon achen?", None

        try:
            res = ctx.fb.publish_post(post_text)
            post_id = res.get("id")
            return f"✅ Page-e post hoye geche!\nPost ID: {post_id}", None
        except Exception as e:
            return f"❌ Post korte shomoshya hoyeche: {e}", None

    # Autonomous AI Intent: "post koro [topic]" or "image banaye post koro"
    return handle_autonomous_ai_post(ctx)

def handle_autonomous_ai_post(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    prompt = ctx.raw_text.strip()
    
    # 1. Ask Gemini to extract image prompt & caption topic
    sys_prompt = (
        f"The user wants to publish a Facebook post: \"{prompt}\".\n"
        f"Extract two things in JSON format:\n"
        f"1. 'image_prompt': An English prompt for AI image generator (e.g. 'cute fluffy cat playing with ball, highly detailed') or null if no image is requested.\n"
        f"2. 'caption': A high-engagement Facebook post caption in Banglish (Bengali in English letters) with emojis and 3 hashtags.\n"
        f"Return ONLY valid JSON."
    )
    ai_raw = gemini_manager.generate(sys_prompt, ctx.sender_name)
    
    image_prompt = None
    caption = f"🚀 {prompt}\n\n#AICommander #Update"

    try:
        # Try parse JSON from response
        json_match = re.search(r'\{.*\}', ai_raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            image_prompt = data.get("image_prompt")
            caption = data.get("caption", caption)
    except Exception:
        # Heuristic fallback
        if "cat" in prompt.lower():
            image_prompt = "cute aesthetic fluffy cat looking at camera, 4k"
            caption = "🐱 Biraler shundor ekta din! Apnader biral kemon ache? Comments-e janan! ❤️\n\n#CatLovers #CuteCats #AICommander"
        else:
            caption = f"✨ {prompt}\n\n#AICommanderBot #DailyUpdate"

    # 2. Publish with image or as text post
    try:
        if image_prompt:
            encoded = urllib.parse.quote(image_prompt)
            seed = random.randint(1000, 999999)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
            
            res = ctx.fb.publish_photo(img_url, caption=caption)
            post_id = res.get("post_id") or res.get("id")
            return (
                f"🎨 AI Image toiri kore Facebook Page-e publish kore diyechi! 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 Caption: {caption}\n"
                f"🆔 Post ID: {post_id}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 Dekhun: https://www.facebook.com/1489379004255673"
            ), img_url
        else:
            res = ctx.fb.publish_post(caption)
            post_id = res.get("id")
            return f"✅ AI post toiri kore publish kore diyechi!\nPost ID: {post_id}", None
    except Exception as e:
        return f"❌ Post publish korte shomoshya hoyeche: {e}", None
