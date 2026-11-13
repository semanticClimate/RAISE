"""
Query Decomposition & Splitting Engine
======================================
Component: `src.features.query.decomposer`
Architecture Layer: Query Processing / Multi-Hop Query Decomposition

Overview:
---------
Decomposes multi-part or compound user questions into 1 to 3 targeted standalone
sub-queries, preventing semantic vector dilution across disparate subjects.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from typing import Any, List, Optional
from src.core.config import models

try:
    from llama_index.core.question_gen.types import SubQuestion
    HAS_LLAMA_INDEX = True
except ImportError:
    SubQuestion = None
    HAS_LLAMA_INDEX = False

logger = logging.getLogger("raise.query.decomposer")


class QueryDecomposerNode:
    """
    Decomposes multi-part or compound user queries into an array of 1 to 3
    targeted standalone sub-queries to prevent semantic vector dilution.
    """

    def __init__(self, vllm_url: Optional[str] = None):
        self.vllm_url = vllm_url or os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1")

    def decompose(self, query: str) -> List[str]:
        q_clean = query.strip()

        # 0. Comparative Multi-Entity Decomposition
        cmp_match = re.match(r"(?i)^compare\s+(.+?)\s+(?:with|to|vs\.?|versus|and)\s+(.+?)$", q_clean)
        if cmp_match:
            entity1, entity2 = cmp_match.group(1).strip(), cmp_match.group(2).strip()
            if len(entity1) > 4 and len(entity2) > 4:
                return [
                    f"What were the metrics and details for {entity1}?",
                    f"What were the metrics and details for {entity2}?",
                ]

        is_compound = False
        conjunctions = [" and ", " as well as ", " along with ", "; ", "? "]
        for c in conjunctions:
            if c in q_clean.lower():
                is_compound = True
                break

        if not is_compound:
            return [q_clean]

        # 1. Attempt LLM decomposition via vLLM if available
        llm_subqueries = self._query_vllm_decomposition(q_clean)
        if llm_subqueries and len(llm_subqueries) > 1:
            return llm_subqueries[:3]

        # 2. Rule-Based Deterministic Decomposition
        parts = re.split(r"(?i)\s+(?:and|as well as|along with)\s+|;\s*|\?\s*", q_clean)
        sub_queries = [p.strip() for p in parts if p.strip() and len(p.strip()) > 8]

        if len(sub_queries) > 1:
            reconstructed = []
            for sq in sub_queries[:3]:
                if not re.match(r"^(who|what|when|where|why|how|list|find)\b", sq, re.IGNORECASE):
                    reconstructed.append(f"Find details on {sq}")
                else:
                    reconstructed.append(sq if sq.endswith("?") else f"{sq}?")
            return reconstructed

        return [q_clean]

    def decompose_subquestions(self, query: str) -> List[Any]:
        """
        Decomposes query into LlamaIndex SubQuestion objects for parallel sub-question execution.
        """
        str_queries = self.decompose(query)
        if HAS_LLAMA_INDEX and SubQuestion is not None:
            return [
                SubQuestion(sub_question=sq, tool_name=f"document_engine_{idx+1}")
                for idx, sq in enumerate(str_queries)
            ]
        return [{"sub_question": sq, "tool_name": f"document_engine_{idx+1}"} for idx, sq in enumerate(str_queries)]

    def _query_vllm_decomposition(self, query: str) -> Optional[List[str]]:
        try:
            url = f"{self.vllm_url}/chat/completions"
            sys_msg = (
                "You are an expert query decomposition agent. Split the compound question into 1 to 3 "
                "independent, single-focus search queries. Return strictly valid JSON array of strings: "
                "[\"sub query 1\", \"sub query 2\"]. If not compound, return [\"original query\"]."
            )
            payload = json.dumps({
                "model": os.getenv("LLM_MODEL_NAME", models.LLM_MODEL_NAME),
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.0,
                "max_tokens": 128,
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"].strip()
                match = re.search(r"\[.*\]", text, re.DOTALL)
                if match:
                    arr = json.loads(match.group(0))
                    if isinstance(arr, list) and all(isinstance(x, str) for x in arr):
                        return arr
        except Exception:
            pass
        return None
