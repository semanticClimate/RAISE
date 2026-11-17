"""
Postgres Chat Store Mixin
=========================
Handles chat message persistence, chronological window queries, session listing,
deletion, and idempotent chat history synchronization in PostgreSQL.
"""

from __future__ import annotations

import json
import hashlib
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("raise.infrastructure.database.postgres.chat")
from .session_mixin import SessionLifecycleMixin


class ChatStoreMixin(SessionLifecycleMixin):
    """Provides methods for chat messaging and session persistence in PostgreSQL."""

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        mode: str = "fast",
        sources: Optional[List[str]] = None,
        active_docs: Optional[List[str]] = None,
        latency_sec: float = 0.0
    ) -> bool:
        sources = sources or []
        lat_float = float(latency_sec or 0.0)
        if not self.is_connected:
            self._memory_chat.setdefault(session_id, []).append({
                "role": role,
                "content": content,
                "text": content,
                "mode": mode,
                "sources": sources,
                "citations": sources,
                "response": {"sources": sources},
                "latency_sec": lat_float,
                "durationSec": lat_float,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            if active_docs is not None:
                self._memory_sessions.setdefault(session_id, {})["attached_docs"] = active_docs
            return True

        conn = self._get_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            # Keep session_metadata in sync so foreign key on message_history is valid
            clean_title = (content[:60] + "...") if len(content) > 60 else content
            docs_json = json.dumps(active_docs) if active_docs is not None else None
            if role == "user":
                if docs_json is not None:
                    cur.execute("""
                        INSERT INTO session_metadata (id, title, attached_docs, created_at, updated_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            title = CASE 
                                WHEN session_metadata.title = 'New Session' OR session_metadata.title LIKE 'Chat %%' 
                                THEN EXCLUDED.title 
                                ELSE session_metadata.title 
                            END,
                            attached_docs = CASE
                                WHEN EXCLUDED.attached_docs IS NOT NULL AND EXCLUDED.attached_docs != '[]'::jsonb
                                THEN EXCLUDED.attached_docs
                                ELSE session_metadata.attached_docs
                            END,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (session_id, clean_title.strip(), docs_json))
                else:
                    cur.execute("""
                        INSERT INTO session_metadata (id, title, created_at, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            title = CASE 
                                WHEN session_metadata.title = 'New Session' OR session_metadata.title LIKE 'Chat %%' 
                                THEN EXCLUDED.title 
                                ELSE session_metadata.title 
                            END,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (session_id, clean_title.strip()))
            else:
                cur.execute("""
                    INSERT INTO session_metadata (id, title, created_at, updated_at)
                    VALUES (%s, 'New Session', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        updated_at = CURRENT_TIMESTAMP;
                """, (session_id,))

            # Save in chat_messages idempotently
            m_hash = hashlib.sha256(f"{session_id}:{role}:{content.strip()}".encode("utf-8")).hexdigest()
            cur.execute("""
                INSERT INTO chat_messages (session_id, role, content, mode, sources, citations, message_hash, latency_sec, duration_sec)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, message_hash) DO UPDATE SET
                    latency_sec = EXCLUDED.latency_sec,
                    duration_sec = EXCLUDED.duration_sec
            """, (session_id, role, content, mode, json.dumps(sources), json.dumps(sources), m_hash, lat_float, lat_float))

            # Keep message_history in sync for relational consistency
            try:
                cur.execute("""
                    INSERT INTO message_history (session_id, role, content, timestamp)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                """, (session_id, role, content))
            except Exception:
                pass

            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to save message in PostgreSQL: {e}")
            return False
        finally:
            self._release_connection(conn)

    def get_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        def _normalize_msg(m: Dict[str, Any]) -> Dict[str, Any]:
            txt = m.get("text") or m.get("content", "")
            srcs = m.get("sources") or m.get("citations", [])
            lat_val = float(m.get("latency_sec") or m.get("durationSec") or m.get("execution_time") or m.get("duration_sec") or 0.0)
            resp_dict = m.get("response")
            if not isinstance(resp_dict, dict):
                resp_dict = {}
            else:
                resp_dict = dict(resp_dict)
            if srcs:
                resp_dict.setdefault("citations", srcs)
                resp_dict.setdefault("sources", srcs)
            if txt:
                resp_dict.setdefault("answer", txt)
                resp_dict.setdefault("grounded_answer", txt)
            return {
                **m,
                "role": m.get("role", "user"),
                "content": txt,
                "text": txt,
                "mode": m.get("mode", "fast"),
                "sources": srcs,
                "citations": srcs,
                "latency_sec": lat_val,
                "durationSec": lat_val,
                "execution_time": lat_val,
                "response": resp_dict if resp_dict else None,
                "created_at": m.get("created_at", datetime.now(timezone.utc).isoformat()),
            }

        if not self.is_connected:
            raw = self._memory_chat.get(session_id, [])[-limit:]
            return [_normalize_msg(m) for m in raw]

        conn = self._get_connection()
        if not conn:
            raw = self._memory_chat.get(session_id, [])[-limit:]
            return [_normalize_msg(m) for m in raw]

        try:
            cur = conn.cursor()
            # Sliding window context query: fetch the N latest messages, then sort chronologically
            cur.execute("""
                SELECT role, content, mode, sources, created_at, COALESCE(latency_sec, duration_sec, 0.0)
                FROM (
                    SELECT id, role, content, mode, sources, created_at, latency_sec, duration_sec
                    FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                ) subquery
                ORDER BY subquery.id ASC
            """, (session_id, limit))
            rows = cur.fetchall()
            cur.close()
            result = []
            for r in rows:
                raw_sources = r[3] if isinstance(r[3], list) else (json.loads(r[3]) if r[3] else [])
                text_content = r[1] or ""
                lat_val = float(r[5] or 0.0)
                result.append({
                    "role": r[0],
                    "content": text_content,
                    "text": text_content,
                    "mode": r[2],
                    "sources": raw_sources,
                    "citations": raw_sources,
                    "response": {
                        "sources": raw_sources,
                        "citations": raw_sources,
                        "answer": text_content,
                        "grounded_answer": text_content,
                    } if raw_sources else None,
                    "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                    "latency_sec": lat_val,
                    "durationSec": lat_val,
                    "execution_time": lat_val
                })
            return result
        except Exception as e:
            logger.error(f"Failed to fetch messages from PostgreSQL: {e}")
            return []
        finally:
            self._release_connection(conn)


    def sync_chat_history(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        title: Optional[str] = None,
        attached_docs: Optional[List[str]] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Idempotently synchronize or restore full chat history and session metadata into PostgreSQL.
        Returns count of synchronized messages.
        """
        if not session_id or not messages:
            return 0

        # Memory fallback update
        normalized_mem = []
        for m in messages:
            txt = m.get("text") or m.get("content", "")
            srcs = (
                m.get("sources")
                or m.get("citations")
                or (m.get("response", {}).get("sources", []) if isinstance(m.get("response"), dict) else [])
            )
            normalized_mem.append({
                **m,
                "role": m.get("role", "user"),
                "content": txt,
                "text": txt,
                "mode": m.get("mode", "fast"),
                "sources": srcs,
                "citations": srcs,
                "response": m.get("response") or ({"sources": srcs} if srcs else None),
                "created_at": m.get("created_at", datetime.now(timezone.utc).isoformat()),
            })
        self._memory_chat[session_id] = normalized_mem
        if attached_docs is not None:
            self._memory_sessions.setdefault(session_id, {})["attached_docs"] = attached_docs

        if not self.is_connected:
            return len(messages)

        conn = self._get_connection()
        if not conn:
            return len(messages)

        synced_count = 0
        try:
            cur = conn.cursor()
            first_user_content = next(
                (m.get("content") or m.get("text", "") for m in messages if m.get("role") == "user"),
                "Restored Session"
            )
            sess_title = title or (first_user_content[:60] + "..." if len(first_user_content) > 60 else first_user_content)
            attached_json = json.dumps(attached_docs) if attached_docs is not None else None

            # 1. Upsert session_metadata
            cur.execute("""
                INSERT INTO session_metadata (id, title, attached_docs, created_at, updated_at)
                VALUES (%s, %s, COALESCE(%s::jsonb, '[]'::jsonb), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    attached_docs = CASE WHEN %s::jsonb IS NOT NULL THEN %s::jsonb ELSE session_metadata.attached_docs END,
                    updated_at = CURRENT_TIMESTAMP;
            """, (session_id, sess_title, attached_json, attached_json, attached_json))

            for idx, msg in enumerate(messages):
                role = msg.get("role", "user")
                content = msg.get("content") or msg.get("text", "")
                if not content:
                    continue
                m_hash = hashlib.sha256(f"{session_id}:{role}:{content.strip()}".encode("utf-8")).hexdigest()
                mode = msg.get("mode", "fast")
                raw_sources = (
                    msg.get("sources")
                    or msg.get("citations")
                    or (msg.get("response", {}).get("sources", []) if isinstance(msg.get("response"), dict) else [])
                )
                raw_citations = msg.get("citations") or raw_sources
                sources_json = json.dumps(raw_sources) if isinstance(raw_sources, list) else json.dumps([])
                citations_json = json.dumps(raw_citations) if isinstance(raw_citations, list) else json.dumps([])
                dur = float(msg.get("latency_sec") or msg.get("durationSec") or msg.get("duration_sec") or 0.0)
                cur.execute("""
                    INSERT INTO chat_messages (session_id, turn_index, role, content, mode, sources, citations, duration_sec, latency_sec, message_hash, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (session_id, message_hash) DO UPDATE SET
                        latency_sec = EXCLUDED.latency_sec,
                        duration_sec = EXCLUDED.duration_sec
                """, (session_id, idx, role, content, mode, sources_json, citations_json, dur, dur, m_hash))
                try:
                    cur.execute("""
                        INSERT INTO message_history (session_id, role, content, timestamp)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    """, (session_id, role, content))
                except Exception:
                    pass
                if cur.rowcount > 0:
                    synced_count += 1

            conn.commit()
            cur.close()
            return synced_count if synced_count > 0 else len(messages)
        except Exception as e:
            logger.error(f"Failed to sync chat history for {session_id} in PostgreSQL: {e}")
            return len(messages)
        finally:
            self._release_connection(conn)
