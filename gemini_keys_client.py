import os
import json
import random
import logging
from typing import List, Optional
try:
    from curl_cffi import requests
except ImportError:
    import requests

logger = logging.getLogger("GeminiKeyManager")
KEYS_FILE = os.path.join(os.path.dirname(__file__), "gemini_keys.json")

class GeminiKeyManager:
    def __init__(self):
        try:
            self.session = requests.Session(impersonate="chrome124")
        except Exception:
            self.session = requests.Session()
        self.keys: List[str] = self.load_keys()
        self.current_index = 0

    def load_keys(self) -> List[str]:
        if os.path.exists(KEYS_FILE):
            try:
                with open(KEYS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [k.strip() for k in data if k.strip()]
                    elif isinstance(data, dict):
                        return [k.strip() for k in data.get("keys", []) if k.strip()]
            except Exception as e:
                logger.error(f"Error loading keys file: {e}")
        return []

    def save_keys(self, keys_list: List[str]):
        self.keys = [k.strip() for k in keys_list if k.strip()]
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.keys, f, indent=2)
        logger.info(f"Saved {len(self.keys)} Gemini API keys.")

    def get_next_key(self) -> Optional[str]:
        if not self.keys:
            return None
        key = self.keys[self.current_index % len(self.keys)]
        self.current_index = (self.current_index + 1) % len(self.keys)
        return key

    def generate(self, prompt: str, user_name: str = "User") -> str:
        """Generate response via official Gemini Flash API or ultra-fast instant fallback."""
        key = self.get_next_key()
        if key:
            # Check if this is an autonomous agent prompt with tools
            if "You are \"AI Commander Agent\"" in prompt or "AVAILABLE TOOLS:" in prompt:
                call_text = prompt
            else:
                call_text = (
                    f"You are AI Commander Bot, an intelligent, helpful, and friendly Facebook Messenger Assistant.\n"
                    f"User: {user_name}\n"
                    f"Message: \"{prompt}\"\n"
                    f"STRICT LANGUAGE RULE: ALWAYS reply in Banglish (Bengali written in English/Latin letters, e.g. 'Ami bhalo achi Mamun bhai, apnar ki khobor?'). NEVER use Bengali script.\n"
                    f"Keep it concise (1-3 natural sentences), helpful, with 1-2 emojis.\n"
                    f"Return ONLY the response text."
                )

            # Call official Gemini Flash REST API (Takes 200-300ms!)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": call_text}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.5,
                    "maxOutputTokens": 800,
                    "thinkingConfig": {"thinkingBudget": 0}
                }
            }
            try:
                r = self.session.post(url, json=payload, timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            return text.strip()
                logger.warning(f"Key call returned {r.status_code}: {r.text[:120]}")
            except Exception as e:
                logger.error(f"Gemini API Key call error: {e}")

        # Ultra-fast Instant Heuristic Engine (< 10ms response time!)
        return self._instant_fallback(prompt, user_name)

    def _instant_fallback(self, prompt: str, user_name: str) -> str:
        p = prompt.lower().strip()
        greetings = ("hi", "hello", "hey", "salam", "assalamualaikum", "kemon acho", "ki khobor", "yo")
        if any(p.startswith(g) or p == g for g in greetings):
            options = [
                f"Hello {user_name} bhai! 👋 Ami AI Commander Bot. Ki bhabe help korte pari bolun? 🚀",
                f"Hey {user_name}! 👋 Shob kisu kemon cholche? Commands dekhte .help likhun!",
                f"Walaikum Assalam {user_name} bhai! ❤️ Ajke apnar jonno ki korte pari?",
                f"Hi {user_name}! 🤖 Ami 24/7 online achi apnake support dite!"
            ]
            return random.choice(options)
        elif "ki korte paro" in p or "help" in p:
            return f"Ami apnake anek bhabe help korte pari {user_name} bhai! 🎨 AI photo banano (.img <prompt>), ⛅ weather check (.weather Dhaka), 🎰 games (.slot) ebong aro onek kisu! Type korun .help!"
        elif "dhonnobad" in p or "thanks" in p or "thank you" in p:
            return f"You're most welcome, {user_name} bhai! ❤️ Shobshomoy pashe achi."
        else:
            return f"Ji {user_name} bhai! Ami apnar kotha bujhte perechi. Apnar proshno niye kono specific help lagle janan ba '.help' likhe shob commands dekhe nin! 🚀"

gemini_manager = GeminiKeyManager()
