import time
import os
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:
    from curl_cffi import requests
    class HTTPAdapter:
        def __init__(self, *args, **kwargs): pass

try:
    from bundle_manager import unpack_bundle
    unpack_bundle()
except Exception:
    pass

from fb_api import FacebookAPI
from ai_engine import AIEngine
from cmds.loader import CommandLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FastMessengerEngine")

CACHE_FILE = os.path.join(os.path.dirname(__file__), "replied_messages.json")
HEARTBEAT_FILE = "/tmp/bot_heartbeat.txt"

class FastMessengerEngine:
    def __init__(self):
        self.fb = FacebookAPI()
        self.ai = AIEngine()
        self.loader = CommandLoader(self.fb)
        self.page_id = self.fb.page_id
        self.page_token = self.fb.page_token
        self.replied_ids = self._load_cache()
        self.replied_comments = set()

        # Thread-safe HTTP session with resilient connection pooling
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=2)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="FastWorker")
        logger.info("FastMessengerEngine initialized with Modular cmds/ System & 8-thread Worker Pool.")

        # Start background daemon threads (NOT consuming ThreadPoolExecutor worker slots)
        threading.Thread(target=self._comment_autopilot_loop, daemon=True, name="CommentAutopilot").start()
        threading.Thread(target=self._live_email_monitor_loop, daemon=True, name="EmailMonitor").start()

    def _comment_autopilot_loop(self):
        """Background thread: Automatically monitors post comments and replies with AI."""
        logger.info("🤖 Comment Auto-Pilot Worker started!")
        while True:
            try:
                # Query feed with higher limit to catch comments across all recent posts
                url = f"https://graph.facebook.com/v20.0/{self.page_id}/feed?fields=id,message,comments{{id,from,message,created_time}}&limit=10&access_token={self.page_token}"
                r = self.session.get(url, timeout=6)
                if r.status_code == 200:
                    posts = r.json().get("data", [])
                    for post in posts:
                        post_text = post.get("message", "")
                        comments = post.get("comments", {}).get("data", [])
                        for c in comments:
                            cid = c.get("id")
                            if cid in self.replied_comments:
                                continue
                            
                            c_sender = c.get("from", {})
                            c_sender_id = c_sender.get("id")
                            c_sender_name = c_sender.get("name", "Friend")
                            c_text = c.get("message", "").strip()

                            # Do not reply to bot's own comments
                            if c_sender_id == self.page_id:
                                continue

                            self.replied_comments.add(cid)
                            logger.info(f"[COMMENT AUTOPILOT] New comment from {c_sender_name}: '{c_text}' on post '{post_text[:30]}'")

                            # Generate AI Reply via Cybervault Multi-Provider Gateway
                            prompt = f"User '{c_sender_name}' commented '{c_text}' on our Facebook post '{post_text}'. Write a friendly, polite 1-sentence reply in Banglish (English letters only) with an emoji."
                            from cybervault_gateway_client import gateway_client
                            reply_text = gateway_client.generate(prompt, c_sender_name)
                            if not reply_text:
                                reply_text = f"Onnek dhonnobad {c_sender_name} bhai! ❤️ Shatei thakun! 🚀"

                            # Post comment reply
                            reply_url = f"https://graph.facebook.com/v20.0/{cid}/comments"
                            self.session.post(reply_url, data={"message": reply_text, "access_token": self.page_token}, timeout=5)
                            logger.info(f"[COMMENT AUTOPILOT] Replied: {reply_text}")

            except Exception as e:
                logger.error(f"[COMMENT AUTOPILOT ERROR] {e}")

            time.sleep(12)  # Check comments every 12 seconds

    def _live_email_monitor_loop(self):
        """Background thread: Monitors active users who enabled .inbox live and alerts them instantly on new emails."""
        from tempgmail import TempGmailClient
        from cmds.context import db
        mail_client = TempGmailClient()
        logger.info("🔔 Live Inbox Notification Monitor started!")

        while True:
            try:
                live_users = db.get_live_users()
                for u in live_users:
                    user_id = u["user_id"]
                    email = u["email"]
                    seen_ids = u["last_seen_msg_ids"]

                    try:
                        inbox_data = mail_client.get_inbox(email)
                        messages = inbox_data.get("messages", [])
                        new_messages = [m for m in messages if m.get("id") and m.get("id") not in seen_ids]

                        if new_messages:
                            logger.info(f"[LIVE MAIL ALERT] Found {len(new_messages)} new email(s) for user {user_id} on {email}")
                            
                            # Cache latest message IDs so user can simply reply '1'
                            cached = [m.get("id") for m in messages[:8] if m.get("id")]
                            db.set_cached_msg_ids(user_id, cached)

                            # Update seen IDs so we don't notify repeatedly
                            for m in new_messages:
                                seen_ids.add(m.get("id"))
                            db.update_last_seen_ids(user_id, list(seen_ids))

                            # Send notification for each new message
                            for m in new_messages:
                                sender = m.get("sender", "Unknown")
                                sender_clean = sender.split("<")[0].strip().replace('"', '') or sender
                                subj = m.get("subject", "No Subject")
                                body = m.get("body_plain", "")
                                otp = mail_client.extract_otp(subj, body)

                                otp_section = f"\n🔥 **OTP / CODE:** `{otp}`\n" if otp else ""

                                notif_text = (
                                    f"🔔 **NOTUN EMAIL ESECHE!**\n"
                                    f"━━━━━━━━━━━━━━━━━━━\n"
                                    f"📬 **Gmail:** `{email}`\n"
                                    f"👤 **From:** {sender_clean}\n"
                                    f"📌 **Subject:** {subj}\n"
                                    f"{otp_section}"
                                    f"━━━━━━━━━━━━━━━━━━━\n"
                                    f"💡 Pura email porte shudhu `1` pathan!\n"
                                    f"🔕 Alert bondho korte: `.inbox off`"
                                )
                                self.send_text(user_id, notif_text)
                    except Exception as err:
                        logger.warning(f"Error checking live inbox for {email}: {err}")
            except Exception as e:
                logger.error(f"[LIVE EMAIL MONITOR ERROR] {e}")

            time.sleep(7)  # Check every 7 seconds

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.replied_ids)[-500:], f, indent=2)
        except Exception:
            pass

    def send_typing_indicator(self, recipient_id: str):
        """Send instant 'typing_on' bubble (sub-200ms)."""
        try:
            self.session.post(
                f"https://graph.facebook.com/v20.0/me/messages?access_token={self.page_token}",
                json={"recipient": {"id": recipient_id}, "sender_action": "typing_on"},
                timeout=3
            )
        except Exception:
            pass

    def _chunk_text(self, text: str, max_chunk_len: int = 1750) -> list:
        """Split text safely so no chunk ever exceeds max_chunk_len, breaking on lines, spaces, or slices."""
        if not text:
            return []
        if len(text) <= max_chunk_len:
            return [text]

        raw_chunks = []
        lines = text.splitlines(keepends=True)
        current = []
        current_len = 0

        for line in lines:
            if len(line) > max_chunk_len:
                if current:
                    raw_chunks.append("".join(current))
                    current = []
                    current_len = 0
                # Split large line by spaces
                words = line.split(" ")
                w_buf = []
                w_len = 0
                for w in words:
                    token = w if w_len == 0 else " " + w
                    if w_len + len(token) > max_chunk_len:
                        if w_buf:
                            raw_chunks.append("".join(w_buf))
                        w_buf = [w]
                        w_len = len(w)
                    else:
                        w_buf.append(token)
                        w_len += len(token)
                if w_buf:
                    raw_chunks.append("".join(w_buf))
            elif current_len + len(line) > max_chunk_len:
                raw_chunks.append("".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line)

        if current:
            raw_chunks.append("".join(current))

        # Hard safety guarantee: clamp any chunk > max_chunk_len
        final_chunks = []
        for c in raw_chunks:
            c_clean = c.strip()
            if not c_clean:
                continue
            if len(c_clean) <= max_chunk_len:
                final_chunks.append(c_clean)
            else:
                for i in range(0, len(c_clean), max_chunk_len):
                    slice_str = c_clean[i:i + max_chunk_len].strip()
                    if slice_str:
                        final_chunks.append(slice_str)
        return final_chunks

    def send_text(self, recipient_id: str, text: str):
        """Deliver text reply with guaranteed sub-1750 char chunking and error logging."""
        if not text:
            return False

        chunks = self._chunk_text(text, max_chunk_len=1750)
        all_ok = True
        for chunk in chunks:
            try:
                r = self.session.post(
                    f"https://graph.facebook.com/v20.0/me/messages?access_token={self.page_token}",
                    json={
                        "recipient": {"id": recipient_id},
                        "messaging_type": "RESPONSE",
                        "message": {"text": chunk}
                    },
                    timeout=8
                )
                if r.status_code != 200:
                    logger.error(f"[SEND_TEXT ERROR] Status {r.status_code}: {r.text}")
                    all_ok = False
            except Exception as e:
                logger.error(f"send_text error: {e}")
                all_ok = False
        return all_ok

    def send_image(self, recipient_id: str, image_path_or_url: str, caption: str = ""):
        """Deliver image attachment via direct URL or local multipart file upload."""
        if caption:
            self.send_text(recipient_id, caption)

        if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):
            try:
                r = self.session.post(
                    f"https://graph.facebook.com/v20.0/me/messages?access_token={self.page_token}",
                    json={
                        "recipient": {"id": recipient_id},
                        "messaging_type": "RESPONSE",
                        "message": {
                            "attachment": {
                                "type": "image",
                                "payload": {"url": image_path_or_url, "is_reusable": True}
                            }
                        }
                    },
                    timeout=15
                )
                return r.status_code == 200
            except Exception as e:
                logger.error(f"send_image url error: {e}")
                return False
        else:
            # Local image file upload via multipart/form-data
            try:
                url = f"https://graph.facebook.com/v20.0/me/messages?access_token={self.page_token}"
                data = {
                    "recipient": json.dumps({"id": recipient_id}),
                    "message": json.dumps({"attachment": {"type": "image", "payload": {"is_reusable": True}}})
                }
                with open(image_path_or_url, "rb") as f:
                    files = {"filedata": (os.path.basename(image_path_or_url), f, "image/png")}
                    r = requests.post(url, data=data, files=files, timeout=40)
                    return r.status_code == 200
            except Exception as e:
                logger.error(f"send_image local file error: {e}")
                return False

    def send_video(self, recipient_id: str, video_path_or_url: str, caption: str = ""):
        """Deliver video attachment via direct URL or multipart file upload."""
        if caption:
            self.send_text(recipient_id, caption)

        if video_path_or_url.startswith("http://") or video_path_or_url.startswith("https://"):
            try:
                r = self.session.post(
                    f"https://graph.facebook.com/v20.0/me/messages?access_token={self.page_token}",
                    json={
                        "recipient": {"id": recipient_id},
                        "messaging_type": "RESPONSE",
                        "message": {
                            "attachment": {
                                "type": "video",
                                "payload": {"url": video_path_or_url, "is_reusable": True}
                            }
                        }
                    },
                    timeout=30
                )
                return r.status_code == 200
            except Exception as e:
                logger.error(f"send_video url error: {e}")
                return False
        else:
            # Local video file upload via multipart/form-data
            try:
                url = f"https://graph.facebook.com/v20.0/me/messages?access_token={self.page_token}"
                data = {
                    "recipient": json.dumps({"id": recipient_id}),
                    "message": json.dumps({"attachment": {"type": "video", "payload": {"is_reusable": True}}})
                }
                with open(video_path_or_url, "rb") as f:
                    files = {"filedata": (os.path.basename(video_path_or_url), f, "video/mp4")}
                    r = requests.post(url, data=data, files=files, timeout=60)
                    if r.status_code != 200:
                        logger.error(f"send_video file upload error [{r.status_code}]: {r.text}")
                    return r.status_code == 200
            except Exception as e:
                logger.error(f"send_video local file error: {e}")
                return False

    def handle_message_async(self, sender_id: str, sender_name: str, text: str, msg_id: str, is_group: bool = False, thread_id: str = "", video_url: str = None, image_url: str = None):
        """Worker thread handler: processes modular commands & AI without blocking the listener."""
        t_start = time.time()
        logger.info(f"[WORKER] Starting async job for {sender_name} ('{text}') [Video: {bool(video_url)}, Image: {bool(image_url)}]")

        # 1. Show instant typing bubble
        self.send_typing_indicator(sender_id)

        # 2. Execute via Modular CommandLoader (cmds/*.py)
        try:
            reply_text, media_url = self.loader.dispatch(
                text=text,
                sender_id=sender_id,
                sender_name=sender_name,
                is_group=is_group,
                thread_id=thread_id,
                video_url=video_url,
                image_url=image_url
            )

            if media_url:
                if media_url.startswith("video_file:"):
                    actual_path = media_url.replace("video_file:", "").strip()
                    self.send_video(sender_id, actual_path, caption=reply_text)
                elif media_url.startswith("image_file:"):
                    actual_path = media_url.replace("image_file:", "").strip()
                    self.send_image(sender_id, actual_path, caption=reply_text)
                elif any(media_url.lower().endswith(ext) for ext in (".mp4", ".mov", ".mkv", ".webm")) or "video" in media_url.lower():
                    self.send_video(sender_id, media_url, caption=reply_text)
                else:
                    self.send_image(sender_id, media_url, caption=reply_text)
            elif reply_text:
                self.send_text(sender_id, reply_text)

            elapsed = time.time() - t_start
            logger.info(f"[WORKER] Completed reply to {sender_name} in {elapsed:.2f}s! 🔥")
        except Exception as e:
            logger.error(f"[WORKER ERROR] {e}")
            self.send_text(sender_id, "Shomoshya hoyeche, ektu por abar cheshta korun.")

    def poll_once(self):
        """Fast polling check (runs every 1 second)."""
        url = f"https://graph.facebook.com/v20.0/{self.page_id}/conversations?fields=messages{{message,from,id,created_time,attachments{{type,payload,image_data,video_data}}}}&limit=4&access_token={self.page_token}"
        try:
            r = self.session.get(url, timeout=4)
            if r.status_code != 200:
                # Log error if token issue
                err = r.json().get("error", {})
                if err.get("code") == 190:
                    logger.warning("[AUTH] Access Token expired. Awaiting refreshed token.")
                return

            data = r.json().get("data", [])
            for conv in data:
                thread_id = conv.get("id", "")
                participants = conv.get("participants", {}).get("data", [])
                is_group = len(participants) > 2

                messages = conv.get("messages", {}).get("data", [])
                if not messages:
                    continue

                latest_msg = messages[0]
                msg_id = latest_msg.get("id")
                sender = latest_msg.get("from", {})
                sender_id = sender.get("id")
                sender_name = sender.get("name", "Friend")
                text = latest_msg.get("message", "").strip()

                if sender_id == self.page_id:
                    continue

                if msg_id in self.replied_ids:
                    continue

                # Ignore very old messages to avoid replying to ancient history on fresh restarts
                created_time_str = latest_msg.get("created_time")
                if created_time_str:
                    try:
                        from datetime import datetime, timezone
                        clean_ts = created_time_str.replace("+0000", "+00:00")
                        msg_time = datetime.fromisoformat(clean_ts)
                        age_sec = (datetime.now(timezone.utc) - msg_time).total_seconds()
                        max_age = 14400 if sender_id in ("61595863212209", "29150849791232816") else 900
                        if age_sec > max_age:
                            self.replied_ids.add(msg_id)
                            continue
                    except Exception:
                        pass

                # Extract attachments (video, image) with comprehensive path checking
                attachments = latest_msg.get("attachments", {}).get("data", [])
                video_url = None
                image_url = None
                for att in attachments:
                    att_type = str(att.get("type", "")).lower()
                    v_data = att.get("video_data") or {}
                    i_data = att.get("image_data") or {}
                    p_data = att.get("payload") or {}

                    v_cand = v_data.get("url") or (p_data.get("url") if att_type == "video" else None)
                    i_cand = i_data.get("url") or (p_data.get("url") if att_type in ("image", "photo") else None)

                    if v_cand and not video_url:
                        video_url = v_cand
                    if i_cand and not image_url:
                        image_url = i_cand

                # Fallback: Scan prior turns from user in current conversation if media was sent in preceding message
                if not video_url and not image_url and len(messages) > 1:
                    for prev_m in messages[1:4]:
                        if prev_m.get("from", {}).get("id") == sender_id:
                            for prev_att in prev_m.get("attachments", {}).get("data", []):
                                p_type = str(prev_att.get("type", "")).lower()
                                prev_v = prev_att.get("video_data", {}).get("url") or (prev_att.get("payload", {}).get("url") if p_type == "video" else None)
                                prev_i = prev_att.get("image_data", {}).get("url") or (prev_att.get("payload", {}).get("url") if p_type in ("image", "photo") else None)
                                if prev_v and not video_url:
                                    video_url = prev_v
                                if prev_i and not image_url:
                                    image_url = prev_i
                            if video_url or image_url:
                                break

                # If user sent media without text, provide a natural greeting prompt
                if not text and image_url:
                    text = "Ami ekta image pathiyechi, dekhun"
                elif not text and video_url:
                    text = "Ami ekta video pathiyechi, dekhun"

                if not text and not video_url and not image_url:
                    continue

                # Mark processed in cache immediately
                self.replied_ids.add(msg_id)
                self._save_cache()

                # Dispatch to background thread pool immediately!
                self.executor.submit(self.handle_message_async, sender_id, sender_name, text, msg_id, is_group, thread_id, video_url, image_url)

        except Exception as e:
            logger.error(f"poll_once error: {e}")

    def run_forever(self):
        logger.info("⚡ Ultra-Fast Polling Loop Started (1.0s interval, non-blocking parallel workers)!")
        while True:
            try:
                try:
                    with open(HEARTBEAT_FILE, "w") as f:
                        f.write(str(time.time()))
                except Exception:
                    pass
                self.poll_once()
            except Exception as e:
                logger.error(f"Polling loop uncaught error: {e}")
            time.sleep(1.0)

if __name__ == "__main__":
    import fcntl
    import sys
    lock_file = "/tmp/fast_messenger_bot.lock"
    try:
        lock_fp = open(lock_file, "a+")
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fp.seek(0)
        lock_fp.truncate()
        lock_fp.write(str(os.getpid()))
        lock_fp.flush()
    except (BlockingIOError, IOError):
        logger.info(f"🔒 PID {os.getpid()}: Another instance of FastMessengerEngine is already running. Exiting gracefully.")
        sys.exit(0)

    engine = FastMessengerEngine()
    engine.run_forever()
