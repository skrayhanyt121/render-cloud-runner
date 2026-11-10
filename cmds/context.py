import os
import json
import sqlite3
import time
from typing import Optional, Dict, Any, List, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "commander_db.sqlite")

# Hardcoded Super Admins (Main Admin UID + Page-Scoped ID)
SUPER_ADMINS = {"61595863212209", "29150849791232816"}

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    balance INTEGER DEFAULT 500,
                    exp INTEGER DEFAULT 0,
                    last_daily INTEGER DEFAULT 0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    name TEXT,
                    prefix TEXT DEFAULT '.',
                    anti_out INTEGER DEFAULT 0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS user_temp_emails (
                    user_id TEXT PRIMARY KEY,
                    email TEXT,
                    live_notify INTEGER DEFAULT 0,
                    last_seen_msg_ids TEXT DEFAULT '[]',
                    cached_msg_ids TEXT DEFAULT '[]',
                    created_at INTEGER
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_admins (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    added_by TEXT,
                    added_at INTEGER
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS user_credits (
                    user_id TEXT PRIMARY KEY,
                    credits INTEGER DEFAULT 0,
                    updated_at INTEGER
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp INTEGER
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversation_history(user_id, timestamp)")

            # Auto-migrate columns if table already existed without them
            for col, col_type in [
                ("live_notify", "INTEGER DEFAULT 0"),
                ("last_seen_msg_ids", "TEXT DEFAULT '[]'"),
                ("cached_msg_ids", "TEXT DEFAULT '[]'")
            ]:
                try:
                    self.conn.execute(f"ALTER TABLE user_temp_emails ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────
    # ROLE & PERMISSION CHECKS
    # ─────────────────────────────────────────────────────────────
    def is_super_admin(self, user_id: str) -> bool:
        return str(user_id).strip() in SUPER_ADMINS

    def is_admin(self, user_id: str) -> bool:
        uid = str(user_id).strip()
        if uid in SUPER_ADMINS:
            return True
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM bot_admins WHERE user_id = ?", (uid,))
            return cur.fetchone() is not None

    def add_admin(self, user_id: str, name: str = "Admin", added_by: str = "Owner") -> bool:
        uid = str(user_id).strip()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO bot_admins (user_id, name, added_by, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET name = excluded.name, added_by = excluded.added_by
            """, (uid, name, added_by, int(time.time())))
            return True

    def remove_admin(self, user_id: str) -> bool:
        uid = str(user_id).strip()
        if uid in SUPER_ADMINS:
            return False  # Cannot remove super admin
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM bot_admins WHERE user_id = ?", (uid,))
            return cur.rowcount > 0

    def get_all_admins(self) -> List[Dict[str, Any]]:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT user_id, name, added_by, added_at FROM bot_admins")
            rows = cur.fetchall()
            admins = [{"user_id": uid, "name": "Owner (Super Admin)", "role": "Super Admin"} for uid in SUPER_ADMINS]
            for r in rows:
                if r[0] not in SUPER_ADMINS:
                    admins.append({"user_id": r[0], "name": r[1], "added_by": r[2], "role": "Admin"})
            return admins

    # ─────────────────────────────────────────────────────────────
    # CREDIT SYSTEM
    # ─────────────────────────────────────────────────────────────
    def get_credits(self, user_id: str) -> int:
        uid = str(user_id).strip()
        if self.is_admin(uid):
            return 999999  # Unlimited for admins
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT credits FROM user_credits WHERE user_id = ?", (uid,))
            row = cur.fetchone()
            return row[0] if row else 0

    def add_credits(self, user_id: str, amount: int) -> int:
        uid = str(user_id).strip()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO user_credits (user_id, credits, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET credits = credits + excluded.credits, updated_at = excluded.updated_at
            """, (uid, amount, int(time.time())))
            cur.execute("SELECT credits FROM user_credits WHERE user_id = ?", (uid,))
            row = cur.fetchone()
            return row[0] if row else 0

    def set_credits(self, user_id: str, amount: int) -> int:
        uid = str(user_id).strip()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO user_credits (user_id, credits, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET credits = excluded.credits, updated_at = excluded.updated_at
            """, (uid, max(0, amount), int(time.time())))
            return max(0, amount)

    def deduct_credit(self, user_id: str, cost: int = 1) -> Tuple[bool, int]:
        uid = str(user_id).strip()
        if self.is_admin(uid):
            return True, 999999  # Admins don't consume credits

        current = self.get_credits(uid)
        if current >= cost:
            new_bal = current - cost
            self.set_credits(uid, new_bal)
            return True, new_bal
        return False, current

    def get_users_with_credits(self) -> List[Dict[str, Any]]:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT user_id, credits, updated_at FROM user_credits WHERE credits > 0 ORDER BY credits DESC")
            rows = cur.fetchall()
            return [{"user_id": r[0], "credits": r[1], "updated_at": r[2]} for r in rows]

    # ─────────────────────────────────────────────────────────────
    # USER & ECONOMY
    # ─────────────────────────────────────────────────────────────
    def get_user(self, user_id: str, name: str = "User") -> Dict[str, Any]:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT user_id, name, balance, exp, last_daily FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                return {"user_id": row[0], "name": row[1], "balance": row[2], "exp": row[3], "last_daily": row[4]}
            else:
                cur.execute("INSERT INTO users (user_id, name, balance, exp, last_daily) VALUES (?, ?, 500, 0, 0)", (user_id, name))
                return {"user_id": user_id, "name": name, "balance": 500, "exp": 0, "last_daily": 0}

    def update_balance(self, user_id: str, delta: int) -> int:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
            cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return row[0] if row else 0

    def set_daily(self, user_id: str, timestamp: int, bonus: int = 500) -> int:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE users SET balance = balance + ?, last_daily = ? WHERE user_id = ?", (bonus, timestamp, user_id))
            cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return row[0] if row else 0

    def get_top_users(self, limit: int = 5):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT name, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
            return cur.fetchall()

    # ─────────────────────────────────────────────────────────────
    # GMAIL TEMP STORAGE
    # ─────────────────────────────────────────────────────────────
    def set_user_email(self, user_id: str, email: str, initial_msg_ids: Optional[List[str]] = None):
        with self.conn:
            cur = self.conn.cursor()
            init_ids = json.dumps(initial_msg_ids or [])
            cur.execute("""
                INSERT INTO user_temp_emails (user_id, email, live_notify, last_seen_msg_ids, cached_msg_ids, created_at)
                VALUES (?, ?, 0, ?, '[]', ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    email = excluded.email,
                    last_seen_msg_ids = excluded.last_seen_msg_ids,
                    cached_msg_ids = '[]',
                    created_at = excluded.created_at
            """, (user_id, email, init_ids, int(time.time())))

    def get_user_email(self, user_id: str) -> Optional[str]:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT email FROM user_temp_emails WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def set_live_notify(self, user_id: str, status: int):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_temp_emails SET live_notify = ? WHERE user_id = ?", (status, user_id))

    def get_live_notify(self, user_id: str) -> int:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT live_notify FROM user_temp_emails WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return row[0] if row else 0

    def get_live_users(self) -> List[Dict[str, Any]]:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT user_id, email, last_seen_msg_ids FROM user_temp_emails WHERE live_notify = 1 AND email IS NOT NULL")
            rows = cur.fetchall()
            results = []
            for r in rows:
                try:
                    seen = json.loads(r[2]) if r[2] else []
                except Exception:
                    seen = []
                results.append({"user_id": r[0], "email": r[1], "last_seen_msg_ids": set(seen)})
            return results

    def update_last_seen_ids(self, user_id: str, ids: List[str]):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_temp_emails SET last_seen_msg_ids = ? WHERE user_id = ?", (json.dumps(list(ids)), user_id))

    def set_cached_msg_ids(self, user_id: str, ids: List[str]):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE user_temp_emails SET cached_msg_ids = ? WHERE user_id = ?", (json.dumps(ids), user_id))

    def get_cached_msg_ids(self, user_id: str) -> List[str]:
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT cached_msg_ids FROM user_temp_emails WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    pass
            return []

    # ─────────────────────────────────────────────────────────────
    # MULTI-TURN CONVERSATION MEMORY
    # ─────────────────────────────────────────────────────────────
    def add_chat_message(self, user_id: str, role: str, content: str):
        """Record chat message for multi-turn conversational context."""
        uid = str(user_id).strip()
        msg = str(content).strip()
        if not uid or not msg:
            return
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO conversation_history (user_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
            """, (uid, role, msg, int(time.time())))
            # Maintain sliding window of last 20 messages per user
            cur.execute("""
                DELETE FROM conversation_history
                WHERE user_id = ? AND id NOT IN (
                    SELECT id FROM conversation_history
                    WHERE user_id = ?
                    ORDER BY id DESC LIMIT 20
                )
            """, (uid, uid))

    def get_recent_chat_history(self, user_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve recent conversation history in chronological order."""
        uid = str(user_id).strip()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT role, content FROM conversation_history
                WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
            """, (uid, limit))
            rows = cur.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def clear_chat_history(self, user_id: str):
        """Clear conversation history for a specific user."""
        uid = str(user_id).strip()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM conversation_history WHERE user_id = ?", (uid,))

db = Database()

class CommandContext:
    def __init__(self, sender_id: str, sender_name: str, raw_text: str, args: str, is_group: bool, thread_id: str, fb_api, cmd_name: str = ""):
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.raw_text = raw_text
        self.args = args
        self.is_group = is_group
        self.thread_id = thread_id
        self.fb = fb_api
        self.db = db
        self.cmd_name = cmd_name

    def is_super_admin(self) -> bool:
        return self.db.is_super_admin(self.sender_id)

    def is_admin(self) -> bool:
        return self.db.is_admin(self.sender_id)

    def get_credits(self) -> int:
        return self.db.get_credits(self.sender_id)

    def deduct_credit(self, cost: int = 1) -> Tuple[bool, int]:
        return self.db.deduct_credit(self.sender_id, cost)
