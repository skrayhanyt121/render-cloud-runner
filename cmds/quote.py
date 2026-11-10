import random
from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "quote",
    "aliases": ["bani", "motivation", "inspire"],
    "category": "Fun & Life",
    "role": 0,
    "description": "Inspiring & motivational quotes",
    "usage": ".quote"
}

QUOTES = [
    "“পরিশ্রম কখনোই বিফলে যায় না, আজ না হয় কাল সফলতা আসবেই।” 💪",
    "“ভুল করা মানে আপনি কিছু নতুন শিখছেন।” 🚀",
    "“ছোট ছোট প্রচেষ্টাই একদিন বিশাল সাফল্যে রূপ নেয়।” ✨",
    "“অন্যদের সফল হতে দেখে হিংসা নয়, অনুপ্রেরণা নিন।” 🌟",
    "“কঠিন সময় দীর্ঘস্থায়ী হয় না, কিন্তু ধৈর্যশীল মানুষ চিরকাল টিকে থাকে।” 🛡️"
]

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    return f"📜 আজকের অনুপ্রেরণা:\n\n{random.choice(QUOTES)}", None
