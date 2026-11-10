"""
Core client for TempGmails.com reverse-engineered API.
Handles Gmail generation, inbox polling, message retrieval, and automatic OTP extraction.
"""

import time
import re
from typing import Dict, Any, List, Optional
from curl_cffi import requests


class TempGmailClient:
    BASE_URL = "https://tempgmails.com/api"

    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://tempgmails.com/",
        }

    def get_random_email(self, exclude: Optional[str] = None) -> Dict[str, Any]:
        """Generate or retrieve a random temporary Gmail account."""
        timestamp = int(time.time() * 1000)
        url = f"{self.BASE_URL}/mail/random?t={timestamp}"
        if exclude:
            url += f"&exclude={exclude}"

        resp = self.session.get(url, headers=self.headers, impersonate="chrome", timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        
        email = data.get("account", {}).get("email")
        messages = data.get("messages", [])
        return {
            "email": email,
            "message_count": len(messages),
            "messages": messages,
        }

    def get_inbox(self, email: str) -> Dict[str, Any]:
        """Fetch inbox contents for a specific email address."""
        timestamp = int(time.time() * 1000)
        clean_email = email.strip()
        url = f"{self.BASE_URL}/mail/{clean_email}?t={timestamp}"

        resp = self.session.get(url, headers=self.headers, impersonate="chrome", timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        messages = data.get("messages", [])
        return {
            "email": clean_email,
            "message_count": len(messages),
            "messages": messages,
        }

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Fetch full HTML and plain text content of a message."""
        clean_id = message_id.strip()
        url = f"{self.BASE_URL}/mail/message/{clean_id}"

        resp = self.session.get(url, headers=self.headers, impersonate="chrome", timeout=self.timeout)
        resp.raise_for_status()
        msg_data = resp.json()

        subject = msg_data.get("subject", "")
        body_plain = msg_data.get("body_plain", "")
        body_html = msg_data.get("body_html", "")

        otp = self.extract_otp(subject, body_plain)
        msg_data["extracted_otp"] = otp

        return msg_data

    def delete_message(self, email: str, message_id: str) -> bool:
        """Delete a single message from the mailbox."""
        url = f"{self.BASE_URL}/mail/{email.strip()}?messageId={message_id.strip()}"
        resp = self.session.delete(url, headers=self.headers, impersonate="chrome", timeout=self.timeout)
        return resp.ok

    def clear_inbox(self, email: str) -> bool:
        """Clear all messages from the mailbox."""
        url = f"{self.BASE_URL}/mail/{email.strip()}"
        resp = self.session.delete(url, headers=self.headers, impersonate="chrome", timeout=self.timeout)
        return resp.ok

    @staticmethod
    def extract_otp(subject: str, body: str) -> Optional[str]:
        """Smart regex OTP extraction from subject and message body."""
        content = f"{subject}\n{body}"

        # Pattern 1: Keywords like Code/OTP/PIN followed by digits
        match = re.search(r'(?i)(?:code|otp|pin|verification|password|verify)[\s\:\-\=\#\.\>]+([0-9]{4,8})\b', content)
        if match:
            return match.group(1)

        # Pattern 2: "is 123456"
        match = re.search(r'(?i)\bis\s+([0-9]{4,8})\b', content)
        if match:
            return match.group(1)

        # Pattern 3: Subject containing prominent standalone digits
        match = re.search(r'\b([0-9]{4,8})\b', subject)
        if match:
            return match.group(1)

        # Pattern 4: Standalone line with only 4-8 digits
        match = re.search(r'^\s*([0-9]{4,8})\s*$', content, re.MULTILINE)
        if match:
            return match.group(1)

        return None

    def wait_for_otp(self, email: str, timeout: int = 120, interval: int = 3, initial_count: int = 0) -> Optional[Dict[str, Any]]:
        """
        Poll inbox until a new message arrives and extract OTP.
        Returns a dict with message details and OTP, or None if timeout reached.
        """
        start_time = time.time()
        known_ids = set()

        # If initial messages exist, record their IDs
        try:
            curr = self.get_inbox(email)
            for m in curr.get("messages", []):
                known_ids.add(m.get("id"))
        except Exception:
            pass

        while time.time() - start_time < timeout:
            time.sleep(interval)
            try:
                inbox = self.get_inbox(email)
                messages = inbox.get("messages", [])
                
                # Check for new messages
                for m in messages:
                    m_id = m.get("id")
                    if m_id not in known_ids:
                        # New message detected! Fetch full details
                        full_msg = self.get_message(m_id)
                        return {
                            "email": email,
                            "sender": full_msg.get("sender"),
                            "subject": full_msg.get("subject"),
                            "otp": full_msg.get("extracted_otp"),
                            "body_plain": full_msg.get("body_plain", "")[:500],
                            "message_id": m_id,
                        }
            except Exception:
                continue

        return None
