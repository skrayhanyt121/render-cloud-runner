import urllib.parse
import urllib.request
import json
from typing import Tuple, Optional
from .context import CommandContext

config = {
    "name": "weather",
    "aliases": ["temp", "abohawa"],
    "category": "Utilities",
    "role": 0,
    "description": "Live weather conditions, temperature, humidity",
    "usage": ".weather <city>"
}

def on_execute(ctx: CommandContext) -> Tuple[Optional[str], Optional[str]]:
    city = ctx.args.strip() if ctx.args else "Dhaka"
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            wdata = json.loads(resp.read().decode())
            current = wdata["current_condition"][0]
            temp = current["temp_C"]
            feels = current["FeelsLikeC"]
            desc = current["weatherDesc"][0]["value"]
            humidity = current["humidity"]
            wind = current["windspeedKmph"]

            report = (
                f"⛅ 𝐖𝐄𝐀𝐓𝐇𝐄𝐑 𝐑𝐄𝐏𝐎𝐑𝐓: {city.title()}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🌡️ Temperature: {temp}°C (Feels: {feels}°C)\n"
                f"☁️ Sky: {desc}\n"
                f"💧 Humidity: {humidity}%\n"
                f"💨 Wind: {wind} km/h\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Have a great day, {ctx.sender_name}! ☀️"
            )
            return report, None
    except Exception:
        return f"❌ {city} shohorer abohawar khobor pawa jayni. Thik shohorer nam likhun (e.g. .weather Dhaka).", None
