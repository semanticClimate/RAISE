"""
Postgres Session Lifecycle Mixin
================================
Purpose:
  Manages session listing, session clearance, and cross-table session deletion
  across PostgreSQL message_history, session_metadata, and chat_messages tables.

Author: RAISE Core Architecture Team
Maintainability: Keep under 190 lines with robust fallback.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger("raise.infrastructure.database.postgres.session")


class SessionLifecycleMixin:
    """Provides methods for managing chat session lifecycle in PostgreSQL."""

    def clear_session(self, session_id: str) -> bool:
        """Clears all messages and metadata for a given session."""
        self._memory_chat.pop(session_id, None)
        self._memory_sessions.pop(session_id, None)
        if not self.is_connected:
            return True

        conn = self._get_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))
            try:
                cur.execute("DELETE FROM message_history WHERE session_id = %s", (session_id,))
                cur.execute("DELETE FROM session_metadata WHERE id = %s", (session_id,))
            except Exception:
                pass
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to clear session in PostgreSQL: {e}")
            return False
        finally:
            self._release_connection(conn)

    def clear_all_sessions(self) -> bool:
        """Clears all chat sessions and messages across all tables."""
        self._memory_chat.clear()
        self._memory_sessions.clear()
        if not self.is_connected:
            return True
        conn = self._get_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM chat_messages;")
            try:
                cur.execute("DELETE FROM message_history;")
                cur.execute("DELETE FROM session_metadata;")
            except Exception:
                pass
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to clear all sessions in PostgreSQL: {e}")
            return False
        finally:
            self._release_connection(conn)

    def list_all_sessions(self) -> List[Dict[str, Any]]:
        """Retrieve all chat sessions, titles, message counts, and timestamps."""
        sessions_dict = {}
        for sid, msgs in self._memory_chat.items():
            first_msg = (msgs[0].get("content") or msgs[0].get("text") or "Untitled Conversation") if msgs else "Untitled Conversation"
            sessions_dict[sid] = {
                "id": sid,
                "thread_id": sid,
                "session_id": sid,
                "title": (first_msg[:60] + "...") if len(first_msg) > 60 else first_msg,
                "message_count": len(msgs),
                "created_at": msgs[0].get("created_at", datetime.now(timezone.utc).isoformat()) if msgs else datetime.now(timezone.utc).isoformat(),
                "updated_at": msgs[-1].get("created_at", datetime.now(timezone.utc).isoformat()) if msgs else datetime.now(timezone.utc).isoformat(),
            }

        if not self.is_connected:
            return list(sessions_dict.values())

        conn = self._get_connection()
        if not conn:
            return list(sessions_dict.values())
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) as msg_count, s.attached_docs
                FROM session_metadata s
                LEFT JOIN message_history m ON s.id = m.session_id
                GROUP BY s.id, s.title, s.created_at, s.updated_at, s.attached_docs
                ORDER BY s.updated_at DESC
            """)
            for r in cur.fetchall():
                sid = r[0]
                attached = r[5] if (len(r) > 5 and r[5] is not None) else []
                if isinstance(attached, str):
                    try:
                        attached = json.loads(attached)
                    except Exception:
                        attached = []
                sessions_dict[sid] = {
                    "id": sid,
                    "thread_id": sid,
                    "session_id": sid,
                    "title": r[1],
                    "created_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
                    "updated_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                    "message_count": int(r[4]),
                    "attached_docs": attached,
                }

            cur.execute("""
                SELECT DISTINCT ON (session_id) session_id, content
                FROM chat_messages
                WHERE role = 'user'
                ORDER BY session_id, created_at ASC
            """)
            first_user_msgs = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("""
                SELECT session_id, COUNT(id), MIN(created_at), MAX(created_at)
                FROM chat_messages
                GROUP BY session_id
                ORDER BY MAX(created_at) DESC
            """)
            for r in cur.fetchall():
                sid = r[0]
                if sid not in sessions_dict:
                    raw_title = first_user_msgs.get(sid) or f"Chat {sid[:8]}"
                    clean_t = (raw_title[:60] + "...") if len(raw_title) > 60 else raw_title
                    sessions_dict[sid] = {
                        "id": sid,
                        "thread_id": sid,
                        "session_id": sid,
                        "title": clean_t,
                        "created_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
                        "updated_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                        "message_count": int(r[1]),
                        "attached_docs": [],
                    }
            cur.close()
            return list(sessions_dict.values())
        except Exception as e:
            logger.error(f"Failed to list sessions from PostgreSQL: {e}")
            return list(sessions_dict.values())
        finally:
            self._release_connection(conn)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages across all tables."""
        self._memory_chat.pop(session_id, None)
        self._memory_sessions.pop(session_id, None)
        if not self.is_connected:
            return True

        conn = self._get_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM message_history WHERE session_id = %s", (session_id,))
            cur.execute("DELETE FROM session_metadata WHERE id = %s", (session_id,))
            cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id} in PostgreSQL: {e}")
            return False
        finally:
            self._release_connection(conn)

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Updates the session title in PostgreSQL and in-memory cache."""
        clean_title = (new_title or "").strip()
        if not clean_title:
            return False

        if session_id in self._memory_sessions:
            if isinstance(self._memory_sessions[session_id], dict):
                self._memory_sessions[session_id]["title"] = clean_title
            else:
                self._memory_sessions[session_id] = {"title": clean_title}

        if not self.is_connected:
            return True

        conn = self._get_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO session_metadata (id, title, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title, updated_at = CURRENT_TIMESTAMP;
            """, (session_id, clean_title))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to rename session {session_id} in PostgreSQL: {e}")
            return False
        finally:
            self._release_connection(conn)

