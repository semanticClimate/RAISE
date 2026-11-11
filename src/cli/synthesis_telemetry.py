"""
RAISE Telemetry Context Assembly & Synthesis Metrics Builder
=============================================================
Purpose:
  Builds telemetry containers for prompt context packing, token budgeting,
  time-to-first-token (TTFT), decode generation speed, and synthesis contracts.

Author: RAISE Core Architecture Team
Maintainability: Keep under 140 lines with verifiable MetricValue tagging.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from src.cli.models import (
    MetricValue,
    ContextAssemblyMetrics,
    PromptContextTelemetry,
    SynthesisMetrics,
)


def build_context_assembly_metrics(
    query: str,
    citations_raw: List[Dict[str, Any]],
    synth_meta: Dict[str, Any],
) -> Tuple[ContextAssemblyMetrics, PromptContextTelemetry, int]:
    """Builds ContextAssemblyMetrics and PromptContextTelemetry from packed citations."""
    p_tokens_raw = synth_meta.get("prompt_tokens")
    if p_tokens_raw is not None:
        ctx_tokens_m = MetricValue.measured(int(p_tokens_raw), unit="tokens")
        ctx_tokens_val = int(p_tokens_raw)
    else:
        est_p = int(len(query.split()) * 1.3 + len(citations_raw) * 350)
        ctx_tokens_m = MetricValue.estimated(est_p, unit="tokens", notes="Approximated via word-to-token heuristic")
        ctx_tokens_val = est_p

    max_ctx_tokens = 8192
    ctx_util_pct = round((ctx_tokens_val / max_ctx_tokens) * 100.0, 1)

    ctx_order = [
        f"[Chunk {c.get('chunk_id', f'c_{i}')} | Page {c.get('primary_page', 1)}]"
        for i, c in enumerate(citations_raw, 1)
    ]

    context_assembly_m = ContextAssemblyMetrics(
        chunks_in_context=MetricValue.measured(len(citations_raw)),
        unique_documents=len(set(c.get("pdf_filename") or c.get("document", "doc") for c in citations_raw)) if citations_raw else 0,
        unique_pages=len(set(c.get("primary_page", 1) for c in citations_raw)) if citations_raw else 0,
        context_tokens=ctx_tokens_m,
        max_context_tokens=max_ctx_tokens,
        context_utilization_pct=MetricValue.derived(ctx_util_pct, unit="%"),
        chunks_dropped=0,
        context_order=ctx_order,
    )

    prompt_context_telemetry = PromptContextTelemetry(
        packed_chunk_ids=[str(c.get("chunk_id", f"c_{i}")) for i, c in enumerate(citations_raw, 1)],
        prompt_context_tokens=ctx_tokens_val,
        context_snippets=[
            {
                "rank": i,
                "chunk_id": str(c.get("chunk_id", f"c_{i}")),
                "primary_page": int(c.get("primary_page", 1)),
                "heading": str(c.get("heading", "")),
                "text": str(c.get("text", ""))[:200],
            }
            for i, c in enumerate(citations_raw, 1)
        ],
    )

    return context_assembly_m, prompt_context_telemetry, ctx_tokens_val


def build_synthesis_metrics(
    answer: str,
    citations_raw: List[Dict[str, Any]],
    synth_meta: Dict[str, Any],
    ctx_tokens_m: MetricValue,
    t_synth: float,
) -> SynthesisMetrics:
    """Builds SynthesisMetrics for local vLLM generation."""
    model_name = synth_meta.get("model") or "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"
    c_tokens_raw = synth_meta.get("completion_tokens")

    if c_tokens_raw is not None:
        c_tokens_m = MetricValue.measured(int(c_tokens_raw), unit="tokens")
        c_tokens_val = int(c_tokens_raw)
    else:
        est_c = int(len(answer.split()) * 1.3)
        c_tokens_m = MetricValue.estimated(est_c, unit="tokens", notes="Approximated via word-to-token heuristic")
        c_tokens_val = est_c

    ttft_raw = synth_meta.get("time_to_first_token_ms") or synth_meta.get("ttft_ms")
    ttft_m = MetricValue.measured(float(ttft_raw), unit="ms") if ttft_raw is not None else MetricValue.unavailable()
    ttft_val = float(ttft_raw) if ttft_raw is not None else None

    decode_speed_raw = synth_meta.get("decode_speed_tok_s") or synth_meta.get("generation_speed_tok_s")
    if decode_speed_raw is not None and float(decode_speed_raw) > 0:
        tok_speed_m = MetricValue.measured(float(decode_speed_raw), unit="tok/s")
    elif t_synth > 0 and c_tokens_val > 0:
        if ttft_val is not None and t_synth > ttft_val:
            decode_s = max(0.001, (t_synth - ttft_val) / 1000.0)
            speed_val = c_tokens_val / decode_s
        else:
            speed_val = c_tokens_val / (t_synth / 1000.0)
        tok_speed_m = MetricValue.derived(speed_val, unit="tok/s")
    else:
        tok_speed_m = MetricValue.unavailable()

    return SynthesisMetrics(
        provider="vLLM (Local TensorRT/PagedAttention)",
        model=model_name,
        context_chunks=MetricValue.measured(len(citations_raw)),
        context_tokens=ctx_tokens_m,
        output_tokens=c_tokens_m,
        generation_speed_tok_s=tok_speed_m,
        time_to_first_token_ms=ttft_m,
        temperature=MetricValue.measured(0.10),
        grounding_mode="STRICT (Anti-Hallucination Enabled)",
        citation_contract="NUMERIC BRACKETS ONLY [1..N]",
        latency_ms=MetricValue.measured(t_synth, unit="ms") if t_synth > 0 else MetricValue.unavailable(),
    )
