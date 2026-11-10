import urllib.parse
import random
from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "img",
    "aliases": ["image", "imagine", "draw", "art", "photo"],
    "category": "AI & Creative",
    "role": 0,
    "description": "Generate high-resolution AI art/images from text",
    "usage": ".img <prompt> [-v for vertical, -l for landscape]"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    prompt = ctx.args.strip()
    if not prompt:
        return (
            f"🎨 𝐀𝐈 𝐈𝐌𝐀𝐆𝐄 𝐆𝐄𝐍𝐄𝐑𝐀𝐓𝐎𝐑\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Usage:\n"
            f"  .img <prompt>          (Square 1:1)\n"
            f"  .img -v <prompt>       (Vertical 9:16 Portrait)\n"
            f"  .img -l <prompt>       (Landscape 16:9 Wallpaper)\n\n"
            f"Examples:\n"
            f"  .img cyberpunk cat in neon city\n"
            f"  .img -v anime girl in rain"
        ), None

    width, height = 1024, 1024
    if "-v" in prompt:
        width, height = 768, 1280
        prompt = prompt.replace("-v", "").strip()
    elif "-l" in prompt:
        width, height = 1280, 768
        prompt = prompt.replace("-l", "").strip()

    prompt_encoded = urllib.parse.quote(prompt)
    seed = random.randint(1000, 9999999)
    image_url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width={width}&height={height}&nologo=true&seed={seed}&model=flux"

    caption = f"🎨 Generated with Flux Engine:\n\"{prompt}\""
    return caption, image_url
