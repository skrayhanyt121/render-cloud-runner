import json
import logging
import re
import urllib.request
import urllib.parse
import random
from typing import Tuple, Optional, Dict, Any

from codespace_cluster import cluster_manager
from tempgmail import TempGmailClient
from cmds.context import db
from cybervault_gateway_client import gateway_client
from gemini_keys_client import gemini_manager
from video_engine import video_engine

logger = logging.getLogger("AutonomousAIAgent")
mail_client = TempGmailClient()

AGENT_SYSTEM_PROMPT = """You are "AI Commander Agent", an autonomous, high-agency AI bot controlling a full cloud infrastructure, Facebook Page, disposable Gmail generator, video processing pipeline, and Linux VMs.
You are communicating directly with users via Facebook Messenger.

CRITICAL RULES:
1. ALWAYS communicate in Banglish (Bengali written using English/Latin alphabet, e.g. "Ami kaj ta kore diyechi!"). NEVER use Bengali Unicode script (বাংলা লিপি).
2. You have FULL ACCESS and REAL TOOLS to control everything.
3. If the user asks you to perform an action, you MUST respond with a JSON block specifying the action and parameters:
```json
{
  "action": "<tool_name>",
  "params": { ... }
}
```
Do NOT add extra chat text around the JSON when calling a tool.

AVAILABLE TOOLS:
- "codespace_status": Check CPU, RAM, memory, disk, and uptime of active Codespace VM. Use this whenever the user asks about Codespace specs, RAM, memory, or status.
  params: {}
- "codespace_stop": Shutdown / turn off the active Codespace VM to save free monthly quota hours. CRITICAL: Use whenever the user asks to stop, turn off, bondho kora, power off, or says 'codespace off kore dao', 'on thakle off koro', 'codespace bondho koro'.
  params: {}
- "codespace_start": Power on / start the Codespace VM. Use whenever the user asks to start, turn on, chalu kora, or says 'codespace on koro', 'chalu koro', 'start koro'.
  params: {}
- "edit_video": Edit a video into 9:16 vertical Reels format (with blurred background), trim, speed up, or render. If user sent a video attachment or link, use this tool.
  params: {"video_url": "<url_if_provided_or_empty>", "instruction": "<edit_instruction_such_as_reels_9:16_or_speed>"}
- "codespace_exec": Run a specific Linux shell/bash command in the 8GB RAM Codespace VM. ALWAYS provide a valid Linux command (e.g. "free -h && uptime -p", "uname -a", "df -h", "ffmpeg -version"). ONLY use when user explicitly asks to run a shell/terminal/bash command. DO NOT use this when user talks about OTP, code, or emails!
  params: {"command": "<valid_linux_bash_command>"}
- "codespace_switch": Switch active burner account (1 to 7).
  params: {"account_number": <1-7>}
- "publish_post": Publish a post to the Facebook Page. If image requested (e.g. 'cat image banai post koro'), include caption in Banglish and image_prompt in English for Flux AI.
  params: {"caption": "<banglish_caption>", "image_prompt": "<english_prompt_for_flux> or null"}
- "generate_image": Generate a 4K AI image for the user in chat.
  params: {"prompt": "<english_detailed_image_prompt>"}
- "create_gmail": Generate a real disposable @gmail.com address for this user.
  params: {}
- "check_inbox": Check incoming emails and extract OTP/recovery codes for this user. CRITICAL: Use this whenever the user says "check koro otp gese", "code ashche kina", "github theke gese", "facebook theke code gese", "mail check koro", "code dao", etc.
  params: {}
- "read_email": Read full email content by index (1, 2) or message ID.
  params: {"target": "<1_or_msg_id>"}
- "grant_credits": Grant credits to a user (Admin only).
  params: {"target_uid": "<uid>", "amount": <number>}
- "get_user_info": Get Facebook UID, role, and credits for a user.
  params: {"target_uid": "<uid_or_null>"}
- "system_stats": Get bot server RAM, CPU, ping and uptime.
  params: {}

If the user is just asking a question, greeting, or chatting, respond directly in friendly, concise Banglish without JSON.
"""

def sanitize_banglish(text: str) -> str:
    """Ensure absolutely zero Bengali Unicode characters appear in the output."""
    if not text:
        return text
    replacements = {
        "সহ": "shoho",
        "এবং": "ebong",
        "বা": "ba",
        "কি": "ki",
        "না": "na",
        "হ্যাঁ": "ha",
        "হাঁ": "ha",
        "পোস্ট": "post",
        "ছবি": "chobi",
        "করুন": "korun",
        "করব": "korbo",
        "ভাই": "bhai",
        "বন্ধু": "bondhu",
        "টাকা": "taka",
        "ক্লিক": "click",
    }
    for bn, en in replacements.items():
        text = text.replace(bn, en)
    # Remove any remaining Bengali Unicode script (\u0980-\u09FF)
    text = re.sub(r'[\u0980-\u09FF]+', '', text)
    return text

class AutonomousAIAgent:
    def __init__(self, fb_api):
        self.fb = fb_api
        self.last_user_videos: Dict[str, str] = {}

    def process_message(self, text: str, sender_id: str, sender_name: str, video_url: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """Processes message through the Autonomous Agent reasoning loop."""
        if video_url:
            self.last_user_videos[sender_id] = video_url

        is_admin = db.is_admin(sender_id)
        is_super = db.is_super_admin(sender_id)
        credits = db.get_credits(sender_id)
        user_email = db.get_user_email(sender_id) or "None"

        context_header = (
            f"[USER CONTEXT: Name={sender_name}, UID={sender_id}, IsAdmin={is_admin}, "
            f"IsSuperAdmin={is_super}, Credits={credits}, ActiveGmail={user_email}]\n"
            f"User Message: {text}"
        )

        # 1. Ask LLM to reason and pick tool or direct answer
        raw_llm_reply = self._call_llm(context_header, sender_name)
        
        # 2. Check if LLM requested a tool execution
        tool_call, intro_prefix = self._extract_json_tool(raw_llm_reply)
        if not tool_call:
            # Direct conversational reply
            return sanitize_banglish(raw_llm_reply), None

        action = tool_call.get("action", "")
        params = tool_call.get("params", {})
        logger.info(f"AI Agent executing tool: {action} with params {params}")

        # 3. Execute tool with permission checks
        reply_text, img_url = self._execute_tool(action, params, sender_id, sender_name, is_admin)
        if intro_prefix:
            reply_text = f"{intro_prefix}\n\n{reply_text}"
        return sanitize_banglish(reply_text), img_url

    def _call_llm(self, prompt: str, user_name: str) -> str:
        url = "http://localhost:8787/v1/chat/completions"
        payload = {
            "model": "auto",
            "messages": [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 800
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer 99c6b16647de712b86b23d215d5c0432073ab9ee76cc776b73a30257098bbaba",
                    "User-Agent": "AIAgent/3.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=18) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning(f"Gateway failed for AI Agent ({e}), using direct Gemini fallback...")

        return gemini_manager.generate(f"{AGENT_SYSTEM_PROMPT}\n\n{prompt}", user_name)

    def _extract_json_tool(self, text: str) -> Tuple[Optional[Dict[str, Any]], str]:
        intro = ""
        # 1. Look for ```json ... ``` blocks
        m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if m:
            try:
                parsed = json.loads(m.group(1))
                if "action" in parsed:
                    start_pos = m.start()
                    prefix = text[:start_pos].strip()
                    return parsed, prefix
            except Exception:
                pass

        # 2. Look for outer curly braces containing "action"
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end+1]
                parsed = json.loads(candidate)
                if "action" in parsed:
                    prefix = text[:start].strip()
                    # Clean markdown code markers if any
                    prefix = prefix.replace("```json", "").replace("```", "").strip()
                    return parsed, prefix
        except Exception:
            pass

        return None, ""

    def _execute_tool(self, action: str, params: Dict[str, Any], sender_id: str, sender_name: str, is_admin: bool) -> Tuple[str, Optional[str]]:
        # Admin / Credit Gate for high-privilege tools
        admin_tools = ("codespace_exec", "codespace_switch", "codespace_stop", "codespace_start", "grant_credits")
        credit_tools = ("publish_post", "create_gmail", "check_inbox", "read_email", "edit_video")

        if action in admin_tools and not is_admin:
            return (
                "⛔ **Access Denied!**\n"
                f"Ei tool-ti shudhu Main Admin (`61595863212209`) execute korte pare.\n"
                f"Apnar UID: `{sender_id}`",
                None
            )

        credit_notice = ""
        if action in credit_tools and not is_admin:
            allowed, rem = db.deduct_credit(sender_id, cost=1)
            if not allowed:
                return (
                    "⛔ **Credit Shesh!**\n"
                    "Ei kaj ti korte 1 credit lagbe, kintu apnar balance 0.\n"
                    "Admin (`61595863212209`)-er kach theke credit nin!",
                    None
                )
            credit_notice = f"\n\n💳 *[1 Credit kete neya hoyeche | Baki: {rem}]*"

        # ─────────────────────────────────────────────────────────────
        # TOOL 1: CODESPACE BASH EXEC
        # ─────────────────────────────────────────────────────────────
        if action == "codespace_exec":
            cmd = params.get("command", "").strip()
            # If conversational query was passed as command, convert to diagnostic bash
            if any(w in cmd.lower() for w in ("ram", "uptime", "memory", "status", "check", "koto", "obostha", "er")):
                cmd = "uname -r && free -h && uptime -p"
            if not cmd:
                cmd = "uname -r && free -h && uptime -p"
            code, out = cluster_manager.run_command(cmd, timeout=45)
            header = "🟢 **Codespace Execution Success**" if code == 0 else f"⚠️ **Codespace Exit: {code}**"
            if len(out) > 1600:
                out = out[:1600] + "\n... [Output truncated]"
            return f"{header}\n━━━━━━━━━━━━━━━━━━━\n```\n{out}\n```", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 2: CODESPACE STATUS
        # ─────────────────────────────────────────────────────────────
        if action == "codespace_status":
            report = cluster_manager.get_status()
            return f"🤖 **AI Agent Cloud Check:**\n\n{report}", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 2B: CODESPACE STOP
        # ─────────────────────────────────────────────────────────────
        if action == "codespace_stop":
            ok, msg = cluster_manager.stop_codespace()
            return f"🤖 **AI Cloud Power Control:**\n\n{msg}", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 2C: CODESPACE START
        # ─────────────────────────────────────────────────────────────
        if action == "codespace_start":
            ok, msg = cluster_manager.start_codespace()
            return f"🤖 **AI Cloud Power Control:**\n\n{msg}", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 2D: EDIT VIDEO (REELS / RESIZE / SPEED)
        # ─────────────────────────────────────────────────────────────
        if action == "edit_video":
            v_url = params.get("video_url", "").strip()
            instruction = params.get("instruction", "convert to 9:16 vertical reels")
            if not v_url and sender_id in self.last_user_videos:
                v_url = self.last_user_videos[sender_id]

            if not v_url:
                return (
                    "⚠️ **Video URL ba Attachment Paini!**\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "Messenger-e video file attachment pathan othoba kono video link din.\n"
                    "Tarpor bolun 'video ta 9:16 reels baniye dao' ba 'edit kore dao'!",
                    None
                )

            import uuid
            uid_str = uuid.uuid4().hex[:8]
            in_file = f"/tmp/ai_bot_videos/input_{uid_str}.mp4"
            out_file = f"/tmp/ai_bot_videos/output_{uid_str}.mp4"

            # 1. Download
            dl_ok = video_engine.download_video(v_url, in_file)
            if not dl_ok:
                return "❌ Video download korte parini. Link ta thik ache kina check korun.", None

            # 2. Edit
            edit_ok, err_msg = video_engine.edit_video(in_file, out_file, instruction)
            if not edit_ok:
                return f"❌ Video editing error: {err_msg}", None

            # 3. Decision on size
            decision = video_engine.deliver_video_decision(out_file)
            size_mb = decision["size_mb"]

            if decision["delivery"] == "direct":
                return (
                    f"🎬 **Video Edit Complete!** (Reels 9:16 Format) 🔥\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 **Size:** {size_mb} MB (Direct Delivery)\n"
                    f"✨ Messenger chat-e direct video pathano hocche!"
                    f"{credit_notice}",
                    f"video_file:{out_file}"
                )
            else:
                dl_url = decision.get("download_url") or "https://files.catbox.moe"
                return (
                    f"🎬 **Video Edit Complete!** 🔥\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 **Size:** {size_mb} MB (>25MB High Quality)\n"
                    f"⚡ Facebook 25MB limit thakay high-speed direct download link toiri kora hoyeche:\n\n"
                    f"📥 **Download Link:**\n{dl_url}\n\n"
                    f"💡 Ei link theke instantly full quality video download korte parben!"
                    f"{credit_notice}",
                    None
                )

        # ─────────────────────────────────────────────────────────────
        # TOOL 3: CODESPACE SWITCH
        # ─────────────────────────────────────────────────────────────
        if action == "codespace_switch":
            acc_num = int(params.get("account_number", 1)) - 1
            success, msg = cluster_manager.switch_account(acc_num)
            return msg, None

        # ─────────────────────────────────────────────────────────────
        # TOOL 4: PUBLISH FACEBOOK POST
        # ─────────────────────────────────────────────────────────────
        if action == "publish_post":
            caption = params.get("caption", "🚀 Update from AI Commander Bot!")
            img_prompt = params.get("image_prompt")
            try:
                if img_prompt:
                    encoded = urllib.parse.quote(img_prompt)
                    seed = random.randint(1000, 999999)
                    img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
                    res = self.fb.publish_photo(img_url, caption=caption)
                    post_id = res.get("post_id") or res.get("id")
                    return (
                        f"🎨 **AI Image toiri kore Page-e publish kore diyechi!** 🚀\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📝 **Caption:** {caption}\n"
                        f"🆔 **Post ID:** `{post_id}`\n"
                        f"🔗 https://www.facebook.com/1489379004255673"
                        f"{credit_notice}"
                    ), img_url
                else:
                    res = self.fb.publish_post(caption)
                    post_id = res.get("id")
                    return f"✅ **Facebook Page-e post publish hoyeche!**\nPost ID: `{post_id}`{credit_notice}", None
            except Exception as e:
                return f"❌ Post publish korte error hoyeche: {e}", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 5: GENERATE IMAGE
        # ─────────────────────────────────────────────────────────────
        if action == "generate_image":
            prompt = params.get("prompt", "futuristic cyberpunk robot, 4k")
            encoded = urllib.parse.quote(prompt)
            seed = random.randint(1000, 999999)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
            return f"✨ Apnar prompt onujayi 4K image toiri korechi:\n\"{prompt}\"", img_url

        # ─────────────────────────────────────────────────────────────
        # TOOL 6: CREATE TEMP GMAIL
        # ─────────────────────────────────────────────────────────────
        if action == "create_gmail":
            try:
                data = mail_client.get_random_email()
                email = data.get("email")
                existing = data.get("messages", [])
                existing_ids = [m.get("id") for m in existing if m.get("id")]
                db.set_user_email(sender_id, email, initial_msg_ids=existing_ids)
                return (
                    f"📧 **Fresh Real Gmail toiri kore diyechi!**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📬 **Gmail Address:**\n"
                    f"`{email}`\n\n"
                    f"💡 Ei email diye je kono jaigay signup/reset korun. Ashar sathe sathe 'inbox check koro' bollei OTP peye jaben!"
                    f"{credit_notice}"
                ), None
            except Exception as e:
                return f"❌ Gmail generate error: {e}", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 7: CHECK GMAIL INBOX
        # ─────────────────────────────────────────────────────────────
        if action == "check_inbox":
            email = db.get_user_email(sender_id)
            if not email:
                return "⚠️ Apnar kono active Gmail nei! Bolun 'ekta gmail banao', ami baniye dibo.", None
            try:
                inbox_data = mail_client.get_inbox(email)
                messages = inbox_data.get("messages", [])
                if not messages:
                    return f"📬 **Inbox (`{email}`):** Ekhono kono email asheni! Kisu second por abar check korte bolun.", None

                cached_ids = []
                msg_list = []
                for i, m in enumerate(messages[:6], 1):
                    mid = m.get("id", "")
                    cached_ids.append(mid)
                    sender = (m.get("sender", "Unknown")).split("<")[0].strip().replace('"', '')
                    subj = m.get("subject", "No Subject")
                    body = m.get("body_plain", "")
                    otp = mail_client.extract_otp(subj, body)
                    otp_badge = f"\n   🔥 **OTP / CODE:** `{otp}`" if otp else ""
                    msg_list.append(f"{i}. 📩 **{sender}**\n   📌 {subj}{otp_badge}\n   👉 Porte: `{i}` pathan")

                db.set_cached_msg_ids(sender_id, cached_ids)
                return (
                    f"📬 **Inbox Check Result (`{email}`):**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    + "\n\n".join(msg_list) +
                    f"\n━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 Je kono email pura porte shudhu tar number pathan (e.g. `1` ba `2`)!"
                    f"{credit_notice}"
                ), None
            except Exception as e:
                return f"❌ Inbox check error: {e}", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 8: READ EMAIL
        # ─────────────────────────────────────────────────────────────
        if action == "read_email":
            target = str(params.get("target", "1")).strip()
            msg_id = target
            if target.isdigit():
                idx = int(target)
                cached = db.get_cached_msg_ids(sender_id)
                if cached and 1 <= idx <= len(cached):
                    msg_id = cached[idx - 1]
            try:
                msg = mail_client.get_message(msg_id)
                sender = msg.get("sender", "Unknown")
                subject = msg.get("subject", "No Subject")
                otp = msg.get("extracted_otp") or mail_client.extract_otp(subject, msg.get("body_plain", ""))
                body = msg.get("body_plain", "").strip() or "No plain text content."
                if len(body) > 1400:
                    body = body[:1400] + "\n\n... [Content truncated]"
                otp_badge = f"🔥 **OTP / CODE:** `{otp}`\n━━━━━━━━━━━━━━━━━━━\n" if otp else ""
                return (
                    f"📨 **EMAIL DETAILS**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **From:** {sender}\n"
                    f"📌 **Subject:** {subject}\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"{otp_badge}"
                    f"📄 **Content:**\n```\n{body}\n```"
                    f"{credit_notice}"
                ), None
            except Exception as e:
                return f"❌ Email read error: {e}", None

        # ─────────────────────────────────────────────────────────────
        # TOOL 9: GRANT CREDITS (Admin Only)
        # ─────────────────────────────────────────────────────────────
        if action == "grant_credits":
            target_uid = str(params.get("target_uid", "")).strip()
            amt = int(params.get("amount", 5))
            if not target_uid:
                return "⚠️ Target UID ullekh korun.", None
            new_bal = db.add_credits(target_uid, amt)
            return (
                f"✅ **AI Agent Granted Credits!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Target UID:** `{target_uid}`\n"
                f"➕ **Added:** +{amt} Credits\n"
                f"💰 **Total Balance:** {new_bal} Credits",
                None
            )

        # ─────────────────────────────────────────────────────────────
        # TOOL 10: USER INFO
        # ─────────────────────────────────────────────────────────────
        if action == "get_user_info":
            target_uid = str(params.get("target_uid") or sender_id).strip()
            role = "👑 Super Admin" if db.is_super_admin(target_uid) else ("⭐ Admin" if db.is_admin(target_uid) else "👤 User")
            creds = "Unlimited" if db.is_admin(target_uid) else f"{db.get_credits(target_uid)} Credits"
            return (
                f"🆔 **USER INFO**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔢 **UID:** `{target_uid}`\n"
                f"🏷️ **Role:** {role}\n"
                f"💳 **Credits:** {creds}",
                None
            )

        # ─────────────────────────────────────────────────────────────
        # TOOL 11: SYSTEM STATS
        # ─────────────────────────────────────────────────────────────
        if action == "system_stats":
            cs_state = cluster_manager.get_state()
            import subprocess
            res = subprocess.run(["bash", "-c", "uptime -p && free -h"], capture_output=True, text=True, timeout=5)
            local_stats = res.stdout.strip()
            return (
                f"⚙️ **System & Cloud Diagnostics:**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"☁️ **Codespace VM State:** `{cs_state}` (Quota Protected)\n"
                f"🖥️ **Bot Host Specs:**\n```\n{local_stats}\n```"
            ), None

        return f"⚠️ Unknown tool: {action}", None
