import os
import json
import random
import logging
import urllib.request
import urllib.error
from typing import List, Optional, Dict, Any

logger = logging.getLogger("GeminiKeyManager")
KEYS_FILE = os.path.join(os.path.dirname(__file__), "gemini_keys.json")

# Verified working models in order of priority
SUPPORTED_MODELS = ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-flash"]

class GeminiKeyManager:
    def __init__(self):
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

    def generate(
        self,
        prompt: str,
        user_name: str = "User",
        history: Optional[List[Dict[str, str]]] = None,
        system_instruction: Optional[str] = None
    ) -> str:
        """
        Generate response via official Gemini API with multi-turn conversation memory,
        verified working models, automatic key rotation, and resilient fallback.
        """
        if not self.keys:
            return self._instant_fallback(prompt, user_name)

        # Build clean alternating multi-turn contents
        contents = []
        if history:
            for turn in history:
                role = "user" if turn.get("role") == "user" else "model"
                text = turn.get("content", "").strip()
                if not text:
                    continue
                # Merge consecutive turns of identical role
                if contents and contents[-1]["role"] == role:
                    contents[-1]["parts"][0]["text"] += f"\n{text}"
                else:
                    contents.append({"role": role, "parts": [{"text": text}]})

            # Ensure first turn is from user
            if contents and contents[0]["role"] != "user":
                contents.pop(0)

        # Append current prompt
        clean_prompt = prompt.strip()
        if contents and contents[-1]["role"] == "user":
            contents[-1]["parts"][0]["text"] += f"\n{clean_prompt}"
        else:
            contents.append({"role": "user", "parts": [{"text": clean_prompt}]})

        # Base payload
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 800
            }
        }

        # Optional System Instruction
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Try supported models and all keys
        for model in SUPPORTED_MODELS:
            num_keys = max(1, len(self.keys))
            for attempt in range(num_keys):
                key = self.get_next_key()
                if not key:
                    break

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                try:
                    body = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=body,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            candidates = data.get("candidates", [])
                            if candidates:
                                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                if text:
                                    return text.strip()
                except urllib.error.HTTPError as he:
                    err_text = ""
                    try:
                        err_text = he.read().decode("utf-8")[:160]
                    except Exception:
                        pass
                    logger.warning(f"Gemini [{model}] Key {attempt+1} returned HTTP {he.code}: {err_text}")
                    if he.code in (404, 400):
                        # Model not supported on this endpoint, try next model
                        break
                    if he.code in (429, 403, 503):
                        # Rate limit or quota or busy, try next key
                        continue
                except Exception as e:
                    logger.error(f"Gemini API call failed [{model}] key {attempt+1}: {e}")

        # Fallback if all API keys and models fail
        return self._instant_fallback(prompt, user_name)

    def _instant_fallback(self, prompt: str, user_name: str) -> str:
        p = prompt.lower().strip()
        greetings = ("hi", "hello", "hey", "salam", "assalamualaikum", "kemon acho", "ki khobor", "yo")
        if any(p.startswith(g) or p == g for g in greetings):
            options = [
                f"Hello {user_name} bhai! 👋 Shob kisu kemon cholche?",
                f"Hey {user_name}! 👋 Bolun ajke ki kaj korben?",
                f"Walaikum Assalam {user_name} bhai! ❤️ Kemon achen?",
                f"Hi {user_name}! 🤖 Ami online achi, janan ki lagbe!"
            ]
            return random.choice(options)
        elif "ki korte paro" in p:
            return f"Ami Codespace VM control (.cloudstatus), video edit (Reels 9:16), disposable Gmail (.gmail), AI image (.img), Facebook post ebong aro onnek kisu korte pari {user_name} bhai! Shob details dekhte `.help` likhun! 🚀"
        elif "help" in p or "cmd" in p:
            return f"Shob commands ebong features dekhte `.help` ba `.menu` likhun {user_name} bhai!"
        elif "dhonnobad" in p or "thanks" in p or "thank you" in p:
            return f"You're welcome, {user_name} bhai! ❤️ Shobshomoy pashe achi."
        else:
            return f"Ji {user_name} bhai! Ami apnar kotha bujhte perechi. Apni specific kono kaj korte chaile bolun, ami kore dibo! 🚀"

gemini_manager = GeminiKeyManager()
