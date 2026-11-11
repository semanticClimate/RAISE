"""
Coreference Resolution & Pronoun Disambiguation
===============================================
Component: `src.features.query.coreference`
Architecture Layer: Query Processing / Conversational Context Resolution

Overview:
---------
Inspects session memory and recent conversation history to resolve ambiguous pronouns
(e.g., 'they', 'their', 'that startup', 'that institution', 'this university')
into self-contained standalone search queries.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("raise.query.coreference")


class CoreferenceResolverNode:
    """
    Inspects thread session memory to resolve ambiguous pronouns and deictic references,
    yielding a self-contained standalone search query.
    """

    PRONOUNS = [
        r"\btheir\b", r"\bthey\b", r"\bits\b", r"\bit\b",
        r"\bthat startup\b", r"\bthat institution\b", r"\bthis university\b",
        r"\bthat project\b", r"\bthat company\b", r"\bthat department\b",
        r"\bshe\b", r"\bhe\b",
    ]

    def __init__(self, session_manager: Optional[Any] = None, vllm_url: Optional[str] = None):
        self.session_manager = session_manager
        self.vllm_url = vllm_url or os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1")

    def resolve(
        self,
        query: str,
        thread_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Resolves ambiguous pronouns to the dominant entity from memory or previous turn.
        Returns: (standalone_query, resolved_entity)
        """
        has_pronoun = any(re.search(pat, query, re.IGNORECASE) for pat in self.PRONOUNS)
        if not has_pronoun:
            return query, None

        # 1. Check SessionMemoryManager if supplied
        if self.session_manager and thread_id:
            resolved, entity = self.session_manager.resolve_coreference(query, thread_id)
            if entity and resolved != query:
                return resolved, entity

        # 2. Check chat_history tuple list
        if chat_history:
            last_turn = chat_history[-1]
            last_text = last_turn.get("human", "") + " " + last_turn.get("ai", "")
            candidates = re.findall(r"\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\b", last_text)
            candidates = [c for c in candidates if c not in ("Human", "AI", "Please", "What", "How", "Tell")]
            if candidates:
                dominant = candidates[0]
                resolved = query
                resolved = re.sub(r"\btheir\b", f"{dominant}'s", resolved, flags=re.IGNORECASE)
                resolved = re.sub(r"\bthey\b", dominant, resolved, flags=re.IGNORECASE)
                resolved = re.sub(r"\bits\b", f"{dominant}'s", resolved, flags=re.IGNORECASE)
                resolved = re.sub(r"\bit\b", dominant, resolved, flags=re.IGNORECASE)
                resolved = re.sub(r"\bthat startup\b", dominant, flags=re.IGNORECASE)
                resolved = re.sub(r"\bthat project\b", dominant, flags=re.IGNORECASE)
                resolved = re.sub(r"\bthat institution\b", dominant, flags=re.IGNORECASE)
                return resolved, dominant

        return query, None
