"""
Intent Routing & Out-of-Scope Firewall
======================================
Component: `src.features.query.intent_router`
Architecture Layer: Query Processing / Security & Intent Routing

Overview:
---------
Classifies query intent and acts as an Out-of-Scope Firewall.
Bypasses databases entirely for greetings, general conversation, or off-topic prompts.

Classification Targets:
- ACADEMIC_RESEARCH: Papers, laboratories, campus overview, rankings, academic programs, document pages, citations, tables, sections.
- FINANCIAL_FACT: Donations, revenues, endowments, budgets, funding, costs.
- MULTI_HOP_RELATION: Who founded, directors, startups incubated, partnerships, alumni roles.
- GENERAL_CHAT: Greetings, casual chit-chat, conversational pleasantries.
- OUT_OF_SCOPE: Adversarial prompts, jailbreaks, non-institutional trivia.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("raise.query.intent_router")


@dataclass
class IntentRouteResult:
    intent: str  # "ACADEMIC_RESEARCH" | "FINANCIAL_FACT" | "MULTI_HOP_RELATION" | "GENERAL_CHAT" | "OUT_OF_SCOPE"
    datasource: str  # "vector search" | "graph query" | "hybrid" | "general chat"
    is_safe: bool
    bypass_retrieval: bool
    refusal_reason: Optional[str] = None
    direct_response: Optional[str] = None


class IntentRouterNode:
    """
    Classifies query intent and acts as an Out-of-Scope Firewall.
    Bypasses databases entirely for greetings, general conversation, or off-topic prompts.
    """

    ADVERSARIAL_PATTERNS = [
        r"(?i)\b(ignore\s+previous\s+instructions|system\s+prompt|delete\s+database|drop\s+table)\b",
        r"(?i)\b(match\s*\(.*\)\s*detach\s*delete|rm\s+-rf|format\s+c:)\b",
        r"(?i)\b(jailbreak|bypass\s+guardrails)\b",
    ]

    GREETING_PATTERNS = [
        r"(?i)^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|howdy)\b",
        r"(?i)\b(?:my\s+name\s+is|call\s+me)\b",
        r"(?i)\b(?:do\s+you\s+know|what\s+is|what's)\s+my\s+name\b",
        r"(?i)\bwho\s+am\s+i\b",
        r"(?i)\bdo\s+you\s+remember\b",
        r"(?i)\b(?:what\s+is|what's)\s+your\s+name\b",
        r"(?i)\bwho\s+are\s+you\b",
        r"(?i)\bwhat\s+can\s+you\s+do\b",
        r"(?i)\bhow\s+are\s+you\b",
        r"(?i)\b(?:thank\s+you|thanks|nice\s+to\s+meet\s+you)\b",
    ]

    OUT_OF_SCOPE_PATTERNS = [
        r"(?i)\b(recipe|bake|cake|poem|lyrics|song|weather\s+in|horoscope|crypto\s+price)\b",
        r"(?i)\b(who\s+is\s+batman|capital\s+of\s+france|prime\s+minister\s+of\s+canada)\b",
        r"(?i)\b(tell\s+me\s+a\s+joke|write\s+a\s+story\s+about)\b",
    ]

    FINANCIAL_KEYWORDS = [
        "revenue", "profit", "ebitda", "income", "expenditure", "budget",
        "crore", "lakh", "turnover", "grant amount", "financial", "balance sheet",
        "funding", "cost", "investment", "valuation"
    ]

    GRAPH_KEYWORDS = [
        "who founded", "who leads", "director", "incubated", "partner",
        "collaborated", "supervises", "invested in", "board member",
        "startup", "spin-off", "connected to", "relationship", "network"
    ]

    ACADEMIC_DOMAIN_TERMS = [
        "university", "institute", "institution", "council", "academy",
        "campus", "faculty", "student", "alumni", "ranking", "rankings",
        "nirf", "qs", "engineering", "science", "biotechnology", "genomics",
        "school", "department", "centre", "center", "lab", "laboratory",
        "degree", "curriculum", "donate", "donation", "endowment", "grant",
        "fellowship", "scholarship", "incubation", "incubator", "startup",
        "patent", "research", "annual report", "audited", "balance sheet",
        "expenditure", "liabilities", "assets", "mandate", "director",
        "page", "pages", "citation", "citations", "document", "documents",
        "report", "reports", "table", "tables", "section", "sections",
        "chapter", "chapters", "figure", "figures", "schedule", "appendix"
    ]

    def __init__(self, vllm_url: Optional[str] = None):
        self.vllm_url = vllm_url or os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1")

    def route(self, query: str) -> IntentRouteResult:
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # Dynamic institution aliases from library
        dynamic_terms = set(self.ACADEMIC_DOMAIN_TERMS)
        try:
            from src.retrieval.fusion import get_library_institutions
            lib_insts = get_library_institutions()
            for aliases in lib_insts.values():
                dynamic_terms.update(aliases)
        except Exception:
            pass

        is_academic_query = any(re.search(rf"\b{re.escape(term)}\b", q_lower) for term in dynamic_terms)

        # 1. Adversarial Injection Check
        for pat in self.ADVERSARIAL_PATTERNS:
            if re.search(pat, q_clean):
                return IntentRouteResult(
                    intent="OUT_OF_SCOPE",
                    datasource="general chat",
                    is_safe=False,
                    bypass_retrieval=True,
                    refusal_reason="Adversarial or hazardous instruction detected.",
                    direct_response="I cannot execute system commands or modify operating parameters. How may I assist your academic research?",
                )

        # 2. General Conversational / Greeting Check
        if not is_academic_query:
            for pat in self.GREETING_PATTERNS:
                if re.search(pat, q_clean, re.IGNORECASE):
                    return IntentRouteResult(
                        intent="GENERAL_CHAT",
                        datasource="general chat",
                        is_safe=True,
                        bypass_retrieval=True,
                        direct_response="Hello! I am RAISE, your institutional intelligence and academic research assistant. How may I assist your research today? Feel free to ask about faculty, departments, publications, patents, admissions, or financial highlights from the reports.",
                    )

            # 3. Off-Topic Guidance
            for pat in self.OUT_OF_SCOPE_PATTERNS:
                if re.search(pat, q_clean):
                    return IntentRouteResult(
                        intent="GENERAL_CHAT",
                        datasource="general chat",
                        is_safe=True,
                        bypass_retrieval=True,
                        direct_response="Hello! While I specialize in analyzing academic reports, technology incubation, and institutional research metrics, I'm happy to help guide you. Feel free to ask any question about the uploaded reports or let me know what you're looking for!",
                    )

        # 4. Attempt vLLM Qwen Intent Routing
        vllm_route = self._query_vllm_intent(q_clean)
        if vllm_route:
            if is_academic_query and vllm_route.intent in ("OUT_OF_SCOPE", "GENERAL_CHAT"):
                if any(w in q_lower for w in self.FINANCIAL_KEYWORDS) or any(w in q_lower for w in ["donate", "donation", "dollar", "billion", "crore", "lakh", "fund"]):
                    return IntentRouteResult(intent="FINANCIAL_FACT", datasource="graph query", is_safe=True, bypass_retrieval=False)
                elif any(w in q_lower for w in self.GRAPH_KEYWORDS):
                    return IntentRouteResult(intent="MULTI_HOP_RELATION", datasource="graph query", is_safe=True, bypass_retrieval=False)
                else:
                    return IntentRouteResult(intent="ACADEMIC_RESEARCH", datasource="vector search", is_safe=True, bypass_retrieval=False)
            return vllm_route

        # 5. Rule-Based Fallback
        if any(w in q_lower for w in self.FINANCIAL_KEYWORDS) or any(w in q_lower for w in ["donate", "donation", "dollar", "billion", "crore", "lakh", "fund"]):
            return IntentRouteResult(
                intent="FINANCIAL_FACT",
                datasource="graph query",
                is_safe=True,
                bypass_retrieval=False,
            )
        if any(w in q_lower for w in self.GRAPH_KEYWORDS):
            return IntentRouteResult(
                intent="MULTI_HOP_RELATION",
                datasource="graph query",
                is_safe=True,
                bypass_retrieval=False,
            )

        return IntentRouteResult(
            intent="ACADEMIC_RESEARCH",
            datasource="vector search",
            is_safe=True,
            bypass_retrieval=False,
        )

    def _query_vllm_intent(self, query: str) -> Optional[IntentRouteResult]:
        """Classify intent using local vLLM endpoint if reachable."""
        try:
            url = f"{self.vllm_url}/chat/completions"
            sys_msg = (
                "You are an intent classifier for an academic institutional intelligence system. Categorize the user's query into strictly one of:\n"
                "- ACADEMIC_RESEARCH (papers, laboratories, campus overview, rankings, academic programs, document pages, citations, tables, sections)\n"
                "- FINANCIAL_FACT (donations, revenues, endowments, budgets, funding, costs)\n"
                "- MULTI_HOP_RELATION (who founded, directors, startups incubated, partnerships, alumni roles)\n"
                "- GENERAL_CHAT (greetings, chit-chat)\n"
                "- OUT_OF_SCOPE (recipes, movies, pop culture, non-institutional trivia)\n"
                "Note: Any query mentioning universities, IITs, engineering colleges, campuses, alumni donations, academic rankings, or asking about specific document pages (e.g., 'page 4', 'page no 4'), citations, or tables MUST be classified as ACADEMIC_RESEARCH or FINANCIAL_FACT.\n"
                "Respond with only the category name."
            )
            payload = json.dumps({
                "model": os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"),
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.0,
                "max_tokens": 16,
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ans = data["choices"][0]["message"]["content"].strip().upper()
                if "OUT_OF_SCOPE" in ans:
                    return IntentRouteResult(
                        intent="OUT_OF_SCOPE",
                        datasource="general chat",
                        is_safe=True,
                        bypass_retrieval=True,
                        direct_response="I specialize in analyzing institutional, academic, and financial reports for higher-education and research institutions. While I cannot answer questions outside this domain, I would be glad to help you explore university governance, faculty research, department statistics, patents, or annual reports! What would you like to investigate?"
                    )
                if "GENERAL_CHAT" in ans:
                    return IntentRouteResult(
                        intent="GENERAL_CHAT",
                        datasource="general chat",
                        is_safe=True,
                        bypass_retrieval=True,
                        direct_response="Hello! How may I assist your academic and institutional research today?"
                    )
                if "FINANCIAL" in ans:
                    return IntentRouteResult(intent="FINANCIAL_FACT", datasource="graph query", is_safe=True, bypass_retrieval=False)
                if "RELATION" in ans:
                    return IntentRouteResult(intent="MULTI_HOP_RELATION", datasource="graph query", is_safe=True, bypass_retrieval=False)
                if "ACADEMIC" in ans:
                    return IntentRouteResult(intent="ACADEMIC_RESEARCH", datasource="vector search", is_safe=True, bypass_retrieval=False)
        except Exception:
            pass
        return None
