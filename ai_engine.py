import os
import sys
import json
import asyncio
from typing import Optional, List, Dict

# Path to gaymini-claude for GeminiClient if needed
sys.path.append("/root/gaymini-claude/sxysifat/src")
sys.path.append("/root/gaymini-claude")

class AIEngine:
    def __init__(self):
        self.cookie_path = "/root/gaymini-claude/gaymini.txt"

    def _call_gemini_sync(self, prompt: str) -> str:
        """Call Gemini Web API or fallback to structured generation."""
        try:
            from anthropic_proxy import get_or_create_client
            from gemini_webapi.constants import Model

            async def _run():
                client = await get_or_create_client(self.cookie_path)
                chat = client.start_chat(model=Model.G_2_5_PRO)
                resp = await chat.send_message(prompt)
                return resp.text

            loop = asyncio.new_event_loop()
            return loop.run_until_complete(_run())
        except Exception as e:
            # High-quality offline fallback prompt generator
            return self._heuristic_fallback(prompt)

    def _heuristic_fallback(self, prompt: str) -> str:
        """Fallback smart generator if remote RPC hangs."""
        prompt_lower = prompt.lower()
        if "reply" in prompt_lower:
            return "Onnek onnek dhonnobad apnar shundor motamot-er jonno! ❤️ Shatei thakun aro notun updates ashche! 🚀"
        elif "tech" in prompt_lower or "ai" in prompt_lower:
            return (
                "🤖 AI er jug-e nijeke shobshomoy ek step egiye rakhun!\n\n"
                "Artificial Intelligence ekhon aar shudhu bhabna noy, eta amader dainandin kaj-ke 10x fast kore dicche. "
                "Apnar kache AI-er kon tool ta shobcheye beshi useful mone hoy? Comments-e janan!\n\n"
                "#ArtificialIntelligence #TechUpdates #AICommander #Innovation"
            )
        else:
            return (
                "🚀 Notun din, notun shombhabona!\n\n"
                "Shobshomoy notun kisu shikhun ebong nijer goal-er dike egiye jan. "
                "Apnader shobar din-ti shundor katuk!\n\n"
                "#StayPositive #AICommanderBot #DailyInspiration"
            )

    def generate_post(self, topic: str, tone: str = "engaging", language: str = "Banglish") -> str:
        """Generate a viral, high-engagement Facebook post."""
        prompt = (
            f"You are an expert social media manager and AI bot for a Facebook Page named 'AI Commander Bot'.\n"
            f"Write a high-engagement Facebook post about: '{topic}'.\n"
            f"Language: {language} (Bengali written in English/Latin letters, e.g. 'Ami ajke apnader sathe share korchi...').\n"
            f"Rules:\n"
            f"- Add proper emojis, clean line breaks, and a clear call-to-action (ask people to comment).\n"
            f"- Add 3-5 relevant hashtags at the bottom.\n"
            f"- Return ONLY the post text without quotes, explanation, or meta-talk."
        )
        return self._call_gemini_sync(prompt).strip()

    def generate_comment_reply(self, post_text: str, user_comment: str, user_name: str = "User") -> str:
        """Generate a smart, friendly context-aware reply to a Facebook comment."""
        prompt = (
            f"You are the AI manager of the Facebook page 'AI Commander Bot'.\n"
            f"Post Context: \"{post_text}\"\n"
            f"User '{user_name}' commented: \"{user_comment}\"\n"
            f"Write a friendly, intelligent, and natural reply to this comment.\n"
            f"Language: Banglish (English letters). Keep it within 1-2 concise sentences with an emoji.\n"
            f"Return ONLY the reply text."
        )
        return self._call_gemini_sync(prompt).strip()
