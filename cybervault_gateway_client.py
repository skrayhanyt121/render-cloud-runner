import json
import logging
import urllib.request
import urllib.error
from typing import Optional

from gemini_keys_client import gemini_manager

logger = logging.getLogger("CybervaultGateway")

class CybervaultGatewayClient:
    def __init__(self, base_url: str = "http://localhost:8787/v1", api_key: str = "99c6b16647de712b86b23d215d5c0432073ab9ee76cc776b73a30257098bbaba"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.system_prompt = (
            "You are AI Commander Bot, an intelligent, helpful, high-speed Facebook AI assistant. "
            "You have direct access to cloud codespaces, video rendering engines, image generators, and automation tools. "
            "CRITICAL LANGUAGE RULE: ALWAYS reply in Banglish (Bengali written using English/Latin alphabet, e.g. 'Ami thik achi, apnar ki lagbe?'). "
            "NEVER use Bengali script/font (বাংলা লিপি). Keep responses concise, helpful, and natural."
        )

    def generate(self, user_prompt: str, user_name: str = "User") -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": "auto",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"{user_name}: {user_prompt}"}
            ],
            "temperature": 0.7,
            "max_tokens": 600
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "AICommanderBot/2.0"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        provider_model = data.get("model", "auto")
                        logger.info(f"Cybervault Gateway reply generated via {provider_model}")
                        return content.strip()
        except Exception as e:
            logger.warning(f"Cybervault Gateway request failed ({e}). Falling back to Gemini Keys Client...")

        # Fallback to direct Gemini key manager
        return gemini_manager.generate(user_prompt, user_name)

# Singleton instance
gateway_client = CybervaultGatewayClient()
