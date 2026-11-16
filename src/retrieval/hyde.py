"""
RAISE Hypothetical Document Embeddings (HyDE) Engine
====================================================
Component: `src.retrieval.hyde`
Architecture Layer: Retrieval Augmentation / Query Expansion
Design Standard: Enterprise-tier, low-latency, modular architecture (<= 400 lines)

Overview:
---------
Bridges the semantic gap for abstract, high-level, or vocabulary-sparse institutional
queries by generating a zero-shot hypothetical excerpt using fast cloud models (Gemini Flash
or Groq Llama 3.3) with local model fallback. The generated hypothetical excerpt provides
dense topical vocabulary aligned with academic annual reports and financial statements.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("raise.retrieval.hyde")

HYDE_PROMPT_TEMPLATE = (
    "You are an academic documentation specialist. Write a concise, 2-3 sentence factual passage "
    "from an official institutional annual report, financial audit, or research publication that "
    "directly answers the following research query. Do not include introductory remarks or disclaimers.\n\n"
    "Research Query: {query}\n\n"
    "Official Report Passage:"
)


class HyDEGenerator:
    """
    Hypothetical Document Embeddings (HyDE) Generator.
    Produces zero-shot synthetic passages to enhance dense semantic retrieval recall.
    """

    def __init__(
        self,
        provider_router: Optional[Any] = None,
        max_tokens: int = 150,
        temperature: float = 0.2,
    ):
        self.provider_router = provider_router
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._cached_hypotheses: Dict[str, str] = {}

    def _get_router(self) -> Optional[Any]:
        if self.provider_router is not None:
            return self.provider_router
        try:
            from src.infrastructure.providers.router import get_provider_router
            self.provider_router = get_provider_router()
            return self.provider_router
        except Exception as exc:
            logger.debug("Provider router initialization note in HyDE: %s", exc)
            return None

    def generate_hypothetical_document(
        self,
        query: str,
        domain_context: str = "academic_annual_report",
    ) -> str:
        """
        Generates a concise hypothetical excerpt for the query using preferred fast cloud providers.
        Falls back to the raw query if generative components are unconfigured.
        """
        clean_query = query.strip()
        if not clean_query:
            return ""

        # Return cached hypothesis if available for exact repeat queries
        cache_key = f"{clean_query}::{domain_context}"
        if cache_key in self._cached_hypotheses:
            return self._cached_hypotheses[cache_key]

        router = self._get_router()
        if not router:
            return clean_query

        start_time = time.perf_counter()
        prompt = HYDE_PROMPT_TEMPLATE.format(query=clean_query)

        try:
            response_text = ""

            # 1. Primary path: Route hypothetical expansion through ProviderRouter using active priority chain
            if hasattr(router, "complete"):
                try:
                    from src.infrastructure.providers.router import InferenceTask
                    task_target = InferenceTask.QUERY_REWRITE
                except Exception:
                    task_target = "query_rewrite"

                try:
                    cand_res = router.complete(
                        prompt=prompt,
                        task=task_target,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                    )
                    if isinstance(cand_res, str) and cand_res.strip():
                        if not any(cand_res.strip().startswith(err_pfx) for err_pfx in ("Error", "Cloud LLM", "ProviderHTTPError", "Inference execution error", "Empty response")):
                            response_text = cand_res.strip()
                except Exception as comp_err:
                    logger.debug("Primary router.complete failed for HyDE: %s. Trying candidate chain...", comp_err)

            # 2. Dynamic fallback path: Iterate through router's active fallback chain (honors user's vLLM/local priority)
            if not response_text:
                candidate_chain = []
                if hasattr(router, "fallback_chain") and router.fallback_chain:
                    disabled = getattr(router, "disabled_providers", set())
                    candidate_chain = [p for p in router.fallback_chain if p not in disabled]
                if not candidate_chain:
                    candidate_chain = ["vllm", "groq", "gemini", "local"]

                for prov_name in candidate_chain:
                    provider = None
                    if hasattr(router, "providers") and isinstance(router.providers, dict):
                        provider = router.providers.get(prov_name)
                    elif hasattr(router, "get_provider_by_name"):
                        try:
                            provider = router.get_provider_by_name(prov_name)
                        except Exception:
                            provider = None

                    if provider and getattr(provider, "is_available", lambda: True)():
                        try:
                            res = None
                            if hasattr(provider, "complete"):
                                try:
                                    candidate = provider.complete(
                                        prompt=prompt,
                                        max_tokens=self.max_tokens,
                                        temperature=self.temperature,
                                    )
                                    if isinstance(candidate, (str, dict)):
                                        res = candidate
                                except Exception as c_err:
                                    logger.debug("Provider %s complete error: %s", prov_name, c_err)

                            if res is None and hasattr(provider, "generate"):
                                try:
                                    candidate = provider.generate(
                                        prompt=prompt,
                                        max_tokens=self.max_tokens,
                                        temperature=self.temperature,
                                    )
                                    if isinstance(candidate, (str, dict)):
                                        res = candidate
                                except Exception as g_err:
                                    logger.debug("Provider %s generate error: %s", prov_name, g_err)

                            if isinstance(res, str) and res.strip():
                                if not any(res.strip().startswith(err_pfx) for err_pfx in ("Error", "Cloud LLM", "ProviderHTTPError")):
                                    response_text = res.strip()
                                    break
                            elif isinstance(res, dict) and res.get("text"):
                                response_text = res["text"].strip()
                                break
                        except Exception as p_err:
                            logger.debug("Provider %s pass failed in HyDE: %s", prov_name, p_err)
                            continue

            # Fallback to router.complete if direct provider pass did not succeed
            if not response_text and hasattr(router, "complete"):
                try:
                    res = router.complete(
                        prompt=prompt,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                    )
                    if isinstance(res, str) and res.strip():
                        if not any(res.strip().startswith(err_pfx) for err_pfx in ("Error", "Cloud LLM", "ProviderHTTPError")):
                            response_text = res.strip()
                except Exception as r_err:
                    logger.debug("Router complete pass note in HyDE: %s", r_err)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            if response_text:
                logger.info(
                    "HyDE passage synthesized successfully in %.1fms (%d chars)",
                    elapsed_ms,
                    len(response_text),
                )
                # Keep cache bounded to 128 recent entries
                if len(self._cached_hypotheses) >= 128:
                    self._cached_hypotheses.pop(next(iter(self._cached_hypotheses)))
                self._cached_hypotheses[cache_key] = response_text
                return response_text
            else:
                logger.debug("HyDE generation produced empty passage; using raw query.")
                return clean_query

        except Exception as exc:
            logger.warning("HyDE generation fallback triggered: %s", exc)
            return clean_query

    def construct_expanded_search_query(
        self,
        original_query: str,
        weight_original: float = 0.5,
    ) -> str:
        """
        Builds a composite query string combining original user inquiry with hypothetical context.
        """
        hypothesis = self.generate_hypothetical_document(original_query)
        if not hypothesis or hypothesis == original_query:
            return original_query

        # Construct weighted composite representation
        return f"{original_query}\n\n[Contextual Blueprint]: {hypothesis}"


_global_hyde_generator: Optional[HyDEGenerator] = None


def get_hyde_generator() -> HyDEGenerator:
    """Returns singleton instance of HyDEGenerator."""
    global _global_hyde_generator
    if _global_hyde_generator is None:
        _global_hyde_generator = HyDEGenerator()
    return _global_hyde_generator
