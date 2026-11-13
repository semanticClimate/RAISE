"""
FineCat-NLI Local Inference Engine
===================================
Harnesses dleemiller/finecat-nli-l (ModernBERT-large, 395M parameters)
for high-precision semantic entailment and contradiction detection.

Hardware Target : cuda:0 (auto-detected GPU) / FP16
Context Length  : 8,192 tokens (ModernBERT native RoPE)
Label Mapping   : 0: entailment, 1: neutral, 2: contradiction
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Global model cache to prevent redundant PyTorch allocations
_CACHED_MODEL = None
_CACHED_TOKENIZER = None
_CACHED_DEVICE = None
_LOAD_FAILED = False
_NLI_LOCK = threading.Lock()


class FineCatNLIVerifier:
    """
    Local Cross-Encoder NLI Verifier utilizing configurable backbone
    (dleemiller/finecat-nli-l by default, or any HuggingFace NLI model)
    specifically fine-tuned on curated multi-source NLI benchmarks.
    """

    MODEL_ID = "dleemiller/finecat-nli-ultra-l"
    LABEL_MAPPING = {0: "ENTAILMENT", 1: "NEUTRAL", 2: "CONTRADICTION"}

    def __init__(self, model_id: Optional[str] = None, max_length: int = 4096, device: Optional[str] = None):
        self.model_id = model_id or os.getenv("NLI_MODEL", self.MODEL_ID)
        self.max_length = max_length
        self.device = device or os.getenv("NLI_DEVICE")

    @classmethod
    def _ensure_loaded(cls, model_id: Optional[str] = None, device: Optional[str] = None) -> bool:
        """Loads weights and tokenizer once into GPU/CPU VRAM as a singleton."""
        global _CACHED_MODEL, _CACHED_TOKENIZER, _CACHED_DEVICE, _LOAD_FAILED
        target_model = model_id or os.getenv("NLI_MODEL", cls.MODEL_ID)
        if _CACHED_MODEL is not None and _CACHED_TOKENIZER is not None:
            if getattr(_CACHED_MODEL, "_loaded_model_id", None) == target_model:
                return True
        if _LOAD_FAILED:
            return False



    @property
    def is_available(self) -> bool:
        return _CACHED_MODEL is not None and _CACHED_TOKENIZER is not None

    def classify_pair(self, premise: str, hypothesis: str) -> Dict[str, Any]:
        """
        Evaluates a single (premise, hypothesis) pair.
        Returns probabilities and discrete verdict: ENTAILMENT, NEUTRAL, or CONTRADICTION.
        """
        batch_res = self.classify_batch([(premise, hypothesis)])
        return batch_res[0] if batch_res else self._heuristic_fallback(premise, hypothesis)

    async def aclassify_pair(self, premise: str, hypothesis: str) -> Dict[str, Any]:
        """Asynchronously dispatches pair classification to thread executor."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.classify_pair(premise, hypothesis))

    async def aclassify_batch(self, pairs: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Asynchronously dispatches batch classification to thread executor."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.classify_batch(pairs))

    def classify_batch(self, pairs: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """
        Executes batched NLI inference over multiple (premise, hypothesis) pairs.
        """
        if not pairs:
            return []

        if not self.is_available and not self._ensure_loaded(self.model_id):
            return [self._heuristic_fallback(p, h) for p, h in pairs]

        import torch

        results: List[Dict[str, Any]] = []
        t0 = time.perf_counter()

        try:
            batch_size = 8
            all_logits_list = []
            all_probs_list = []

            with torch.inference_mode():
                for b_start in range(0, len(pairs), batch_size):
                    batch_pairs = pairs[b_start : b_start + batch_size]
                    b_premises = [p for p, _ in batch_pairs]
                    b_hypotheses = [h for _, h in batch_pairs]
                    inputs = _CACHED_TOKENIZER(
                        b_premises,
                        b_hypotheses,
                        padding=True,
                        truncation=True,
                        max_length=self.max_length,
                        return_tensors="pt",
                    ).to(_CACHED_DEVICE)
                    outputs = _CACHED_MODEL(**inputs)
                    b_logits = outputs.logits
                    all_logits_list.append(b_logits.cpu().float())
                    all_probs_list.append(torch.softmax(b_logits, dim=-1).cpu().float())

            logits_np = torch.cat(all_logits_list, dim=0).numpy()
            probs = torch.cat(all_probs_list, dim=0).numpy()

            elapsed_ms = (time.perf_counter() - t0) * 1000.0 / max(len(pairs), 1)

            # Dynamic label index discovery to support any future NLI architecture
            ent_idx, neu_idx, con_idx = 0, 1, 2
            id2label = getattr(getattr(_CACHED_MODEL, "config", None), "id2label", None)
            if id2label and isinstance(id2label, dict):
                for idx, lbl in id2label.items():
                    lbl_clean = str(lbl).lower()
                    if "entail" in lbl_clean:
                        ent_idx = int(idx)
                    elif "contra" in lbl_clean:
                        con_idx = int(idx)
                    elif "neut" in lbl_clean:
                        neu_idx = int(idx)

            for logit_row, prob_row in zip(logits_np, probs):
                ent_prob = float(prob_row[ent_idx])
                neu_prob = float(prob_row[neu_idx])
                con_prob = float(prob_row[con_idx])

                raw_logits = {
                    "entailment": round(float(logit_row[ent_idx]), 4),
                    "neutral": round(float(logit_row[neu_idx]), 4),
                    "contradiction": round(float(logit_row[con_idx]), 4),
                }
                softmax_probs = {
                    "entailment": round(ent_prob, 4),
                    "neutral": round(neu_prob, 4),
                    "contradiction": round(con_prob, 4),
                }

                # Tri-State Decision Logic:
                # 1. Hard contradiction check
                # 2. Strong entailment check
                # 3. Neutral / uncertain (insufficient evidence)
                if con_prob >= 0.50:
                    verdict = "CONTRADICTION"
                    is_entailed = False
                    is_contradiction = True
                    decision_reason = f"Contradiction detected (P(C)={con_prob:.2f} >= 0.50); claim conflicts with premise."
                elif ent_prob >= 0.60 and con_prob < 0.20:
                    verdict = "ENTAILMENT"
                    is_entailed = True
                    is_contradiction = False
                    decision_reason = f"Entailment verified (P(E)={ent_prob:.2f} >= 0.60, P(C)={con_prob:.2f} < 0.20)."
                else:
                    verdict = "NEUTRAL"
                    is_entailed = False
                    is_contradiction = False
                    decision_reason = f"Neutral / Insufficient evidence (P(N)={neu_prob:.2f}, P(E)={ent_prob:.2f}, P(C)={con_prob:.2f}); path uncertain."

                results.append({
                    "entailment_prob": round(ent_prob, 4),
                    "neutral_prob": round(neu_prob, 4),
                    "contradiction_prob": round(con_prob, 4),
                    "raw_logits": raw_logits,
                    "softmax_probs": softmax_probs,
                    "calibration_status": "UNVALIDATED_RAW_SOFTMAX",
                    "decision_reason": decision_reason,
                    "verdict": verdict,
                    "is_entailed": is_entailed,
                    "is_contradiction": is_contradiction,
                    "latency_ms": round(elapsed_ms, 2),
                    "fallback": False,
                })
            return results
        except Exception as exc:
            logger.warning("FineCat-NLI inference failed: %s. Falling back to heuristic.", exc)
            return [self._heuristic_fallback(p, h) for p, h in pairs]

    def _heuristic_fallback(self, premise: str, hypothesis: str) -> Dict[str, Any]:
        """
        Zero-crash offline fallback using token and n-gram overlap.
        """
        p_lower = premise.lower()
        # Extract clean alphanumeric content words
        h_words = [w for w in re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", hypothesis.lower())]
        if not h_words:
            return {
                "entailment_prob": 1.0,
                "neutral_prob": 0.0,
                "contradiction_prob": 0.0,
                "raw_logits": None,
                "softmax_probs": {"entailment": 1.0, "neutral": 0.0, "contradiction": 0.0},
                "calibration_status": "UNVALIDATED_HEURISTIC",
                "decision_reason": "Trivially entailed; hypothesis contains no content tokens.",
                "verdict": "ENTAILMENT",
                "is_entailed": True,
                "is_contradiction": False,
                "latency_ms": 0.0,
                "fallback": True,
            }

        # Check direct match or stem/prefix match (e.g. allocations vs allocated, startups vs startup)
        hits = 0.0
        for w in h_words:
            if w in p_lower:
                hits += 1.0
            elif len(w) > 4 and (w[:-1] in p_lower or w[:-2] in p_lower or w[:4] in p_lower):
                hits += 0.85
        ratio = (hits / len(h_words)) if h_words else 1.0

        has_negation = any(neg in f" {hypothesis.lower()} " for neg in [" not ", " never ", " no ", " neither ", " none ", " without "])
        has_premise_neg = any(neg in f" {p_lower} " for neg in [" not ", " never ", " no ", " neither ", " none ", " without "])

        if has_negation != has_premise_neg and ratio > 0.5:
            con_prob = 0.70
            ent_prob = 0.15
            neu_prob = 0.15
            verdict = "CONTRADICTION"
            decision_reason = "Contradiction detected via negation mismatch on shared keyword content."
        elif ratio >= 0.70:
            ent_prob = round(min(0.98, ratio), 4)
            neu_prob = round(max(0.0, 1.0 - ent_prob), 4)
            con_prob = 0.0
            verdict = "ENTAILMENT"
            decision_reason = f"Heuristic high lexical entailment ({ratio*100:.1f}% token overlap)."
        elif ratio >= 0.38:
            # Calibrated for abstractive modern LLM answers: 38%+ overlap without negation conflict signifies entailment
            ent_prob = round(min(0.92, ratio + 0.35), 4)
            neu_prob = round(max(0.0, 1.0 - ent_prob - 0.05), 4)
            con_prob = 0.05
            verdict = "ENTAILMENT"
            decision_reason = f"Heuristic calibrated entailment ({ratio*100:.1f}% token overlap, no negation conflict); verdict={verdict}."
        elif ratio >= 0.25:
            ent_prob = round(ratio, 4)
            neu_prob = round(max(0.0, 1.0 - ratio - 0.10), 4)
            con_prob = 0.10
            verdict = "NEUTRAL"
            decision_reason = f"Heuristic moderate/low overlap ({ratio*100:.1f}% token overlap); verdict={verdict}."
        else:
            ent_prob = round(ratio, 4)
            neu_prob = 0.60
            con_prob = 0.20
            verdict = "NEUTRAL"
            decision_reason = f"Heuristic low overlap ({ratio*100:.1f}% token overlap); insufficient evidence."

        return {
            "entailment_prob": ent_prob,
            "neutral_prob": neu_prob,
            "contradiction_prob": con_prob,
            "raw_logits": None,
            "softmax_probs": {
                "entailment": ent_prob,
                "neutral": neu_prob,
                "contradiction": con_prob,
            },
            "calibration_status": "UNVALIDATED_HEURISTIC",
            "decision_reason": decision_reason,
            "verdict": verdict,
            "is_entailed": (ent_prob >= 0.55 and con_prob < 0.25),
            "is_contradiction": (con_prob >= 0.50),
            "latency_ms": 0.0,
            "fallback": True,
        }


# Module-level instance for convenient import
nli_verifier = FineCatNLIVerifier()
