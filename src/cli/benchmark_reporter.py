"""
RAISE Benchmark Reporter & Forensic Scorecard
==============================================
Purpose:
  Formats side-by-side Ground Truth vs Pipeline verification scorecards,
  exports structured forensic failure traces, and renders the comprehensive
  multi-target benchmark summary matrix.

Author: RAISE Core Architecture Team
Maintainability: Keep under 260 lines with clean ANSI formatting.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.cli.models import TelemetryFrame
from src.cli.renderer import C
from src.cli.commands import sanitize_path


def compute_question_target_metrics(
    frame: TelemetryFrame,
    req_keywords: List[str],
    tier: int,
    q_text: str,
    target_doc: Optional[str],
    recovery_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Computes all 11 target evaluation metrics for a single benchmark query."""
    ans_clean = frame.answer.strip()
    retrieved_text = " ".join([c.excerpt for c in frame.provenance.citations]).lower()
    kw_in_evidence = [kw for kw in req_keywords if kw.lower() in retrieved_text]
    kw_in_answer = [kw for kw in req_keywords if kw.lower() in ans_clean.lower()]
    kw_misses = [kw for kw in req_keywords if kw not in kw_in_answer]

    ev_cov = round((len(kw_in_evidence) / len(req_keywords)) * 100.0, 1) if req_keywords else 100.0

    is_gate_ok = frame.quality.is_gate_passed
    strict_correct = (is_gate_ok and (not req_keywords or len(kw_in_answer) == len(req_keywords)))
    outcome_status = "PASS" if strict_correct else ("BLOCKED" if not is_gate_ok else "MISMATCH")

    gate_info = frame.chain_completeness_gate or {}
    required_hops = int(gate_info.get("required_hops", 2 if tier in (2, 3) else 1))
    hops_found = int(gate_info.get("completed_hops", 0))
    if hops_found == 0 and len(frame.provenance.citations) > 0:
        hops_found = 1
        if required_hops > 1 and recovery_meta.get("recovery_succeeded"):
            hops_found = 2
    hop_recall_pct = round((hops_found / max(1, required_hops)) * 100.0, 1)

    if tier == 1 and not gate_info.get("discovered_bridge_entity"):
        bridge_recall_pct = 100.0
    else:
        bridge_recall_pct = 100.0 if (
            len(recovery_meta.get("graph_bridges_found", [])) > 0
            or hops_found >= 2
            or gate_info.get("status") == "PASSED"
        ) else 0.0

    total_chunks_in_ctx = frame.context_assembly.chunks_in_context.value or len(frame.provenance.citations)
    cited_chunks_cnt = len(frame.provenance.citations)
    ctx_precision = round((cited_chunks_cnt / max(1, total_chunks_in_ctx)) * 100.0, 1)

    is_abstention = (not is_gate_ok or not ans_clean)
    is_trap = (tier == 4 or "unanswerable" in q_text.lower())
    correct_abstention = 1.0 if (is_abstention and is_trap) else 0.0
    recoverable_abstention = 1.0 if (is_abstention and not is_trap and target_doc) else 0.0

    resolved_entities_cnt = len([k for k in req_keywords if not any(c.isdigit() for c in k) and k.lower() in retrieved_text])
    total_named_entities = len([k for k in req_keywords if not any(c.isdigit() for c in k)])
    entity_res_acc = round((resolved_entities_cnt / max(1, total_named_entities)) * 100.0, 1) if total_named_entities > 0 else 100.0

    is_table_q = (tier == 1 or any(term in q_text.lower() for term in ["table", "schedule", "row"]))
    table_acc = 100.0 if (is_table_q and strict_correct) else (0.0 if is_table_q else 100.0)

    temp_matches = [kw for kw in req_keywords if re.search(r"\b(20\d\d|19\d\d)\b", kw) and kw.lower() in ans_clean.lower()]
    temp_total = [kw for kw in req_keywords if re.search(r"\b(20\d\d|19\d\d)\b", kw)]
    temporal_acc = round((len(temp_matches) / max(1, len(temp_total))) * 100.0, 1) if temp_total else 100.0

    num_matches = [kw for kw in req_keywords if any(c.isdigit() for c in kw) and kw.lower() in ans_clean.lower()]
    num_total = [kw for kw in req_keywords if any(c.isdigit() for c in kw)]
    numerical_acc = round((len(num_matches) / max(1, len(num_total))) * 100.0, 1) if num_total else 100.0

    return {
        "ans_clean": ans_clean,
        "strict_correct": strict_correct,
        "outcome_status": outcome_status,
        "hop_recall_pct": hop_recall_pct,
        "hops_found": hops_found,
        "required_hops": required_hops,
        "bridge_recall_pct": bridge_recall_pct,
        "ev_cov": ev_cov,
        "kw_in_evidence": kw_in_evidence,
        "kw_in_answer": kw_in_answer,
        "kw_misses": kw_misses,
        "ctx_precision": ctx_precision,
        "table_acc": table_acc,
        "temporal_acc": temporal_acc,
        "numerical_acc": numerical_acc,
        "num_matches": num_matches,
        "num_total": num_total,
        "correct_abstention": correct_abstention,
        "recoverable_abstention": recoverable_abstention,
        "entity_res_acc": entity_res_acc,
    }


def print_provenance_scorecard(
    gt_answer: str,
    ans_clean: str,
    strict_correct: bool,
    hop_recall_pct: float,
    hops_found: int,
    required_hops: int,
    bridge_recall_pct: float,
    ev_cov: float,
    kw_in_evidence_cnt: int,
    req_keywords_cnt: int,
    ctx_precision: float,
    table_acc: float,
    temporal_acc: float,
    numerical_acc: float,
    num_matches_cnt: int,
    num_total_cnt: int,
    outcome_status: str,
    kw_misses: List[str],
) -> None:
    """Prints question-level side-by-side ground truth vs pipeline answer scorecard."""
    print(f"\n{C.SECTION}══════════════════════════════════════════════════════════════════════════{C.RESET}")
    print(f" {C.TITLE}🔍 BENCHMARK PROVENANCE & FACTUAL VERIFICATION SCORECARD{C.RESET}")
    print(f"{C.SECTION}══════════════════════════════════════════════════════════════════════════{C.RESET}")

    print(f"\n {C.SECTION}1. Ground Truth Reference (From PDF):{C.RESET}")
    if gt_answer:
        for line in gt_answer.strip().split("\n"):
            print(f"    {C.CYAN}{line}{C.RESET}")
    else:
        print(f"    {C.MUTED}(No ground truth text recorded in benchmark file){C.RESET}")

    print(f"\n {C.SECTION}2. RAISE GraphRAG Pipeline Answer:{C.RESET}")
    if ans_clean:
        for line in ans_clean.split("\n"):
            print(f"    {C.WHITE}{line}{C.RESET}")
    else:
        print(f"    {C.DANGER}[NO ANSWER GENERATED / REFUSAL ISSUED]{C.RESET}")

    print(f"\n {C.ACCENT}EVALUATION TARGET METRICS:{C.RESET}")
    print(f"   • Strict Correctness  : {C.SUCCESS if strict_correct else C.DANGER}{'100%' if strict_correct else '0%'}{C.RESET}")
    print(f"   • Hop Recall          : {C.NUM}{hop_recall_pct:.1f}%{C.RESET} ({hops_found}/{required_hops} hops)")
    print(f"   • Bridge Recall       : {C.NUM}{bridge_recall_pct:.1f}%{C.RESET}")
    print(f"   • Evidence Coverage   : {C.NUM}{ev_cov:.1f}%{C.RESET} ({kw_in_evidence_cnt}/{req_keywords_cnt} in chunks)")
    print(f"   • Context Precision   : {C.NUM}{ctx_precision:.1f}%{C.RESET}")
    print(f"   • Table Accuracy      : {C.NUM}{table_acc:.1f}%{C.RESET}")
    print(f"   • Temporal Accuracy   : {C.NUM}{temporal_acc:.1f}%{C.RESET}")
    print(f"   • Numerical Accuracy  : {C.NUM}{numerical_acc:.1f}%{C.RESET} ({num_matches_cnt}/{num_total_cnt} matched)")
    print(f"   • Quality Gate Verdict: {C.SUCCESS if outcome_status == 'PASS' else C.DANGER}{outcome_status}{C.RESET}")

    if kw_misses:
        print(f"   {C.MUTED}Missing Tokens:{C.RESET} " + ", ".join([f"{C.WARN}'{m}'{C.RESET}" for m in kw_misses]))


def export_benchmark_failure_trace(
    failures_dir: Path,
    q_id: str,
    tier: int,
    q_text: str,
    target_doc: Optional[str],
    req_keywords: List[str],
    gt_answer: str,
    strict_correct: bool,
    hop_recall_pct: float,
    bridge_recall_pct: float,
    ev_cov: float,
    ctx_precision: float,
    correct_abstention: float,
    recoverable_abstention: float,
    entity_res_acc: float,
    table_acc: float,
    temporal_acc: float,
    numerical_acc: float,
    recovery_meta: Dict[str, Any],
    outcome_status: str,
    frame: TelemetryFrame,
    kw_in_answer: List[str],
    kw_in_evidence: List[str],
    kw_misses: List[str],
) -> None:
    """Exports structured forensic JSON failure trace for offline diagnostics."""
    f_class_val = (
        frame.debug_summary.failure_class.value
        if hasattr(frame.debug_summary.failure_class, "value")
        else str(frame.debug_summary.failure_class)
    )
    trace_payload = {
        "benchmark_question": {
            "q_id": q_id,
            "tier": tier,
            "question": q_text,
            "target_document": target_doc,
            "required_keywords": req_keywords,
            "ground_truth_answer": gt_answer,
        },
        "target_metrics": {
            "strict_correctness": 1.0 if strict_correct else 0.0,
            "hop_recall": hop_recall_pct,
            "bridge_recall": bridge_recall_pct,
            "evidence_coverage": ev_cov,
            "context_precision": ctx_precision,
            "correct_abstention": correct_abstention,
            "recoverable_abstention": recoverable_abstention,
            "entity_resolution_accuracy": entity_res_acc,
            "table_accuracy": table_acc,
            "temporal_accuracy": temporal_acc,
            "numerical_accuracy": numerical_acc,
        },
        "recovery_loop": recovery_meta,
        "pipeline_outcome": {
            "outcome_status": outcome_status,
            "quality_gate_passed": frame.quality.is_gate_passed,
            "quality_gate_decision": frame.quality.decision,
            "rejection_reason": frame.quality.rejection_reason,
            "failure_class": f_class_val,
            "root_cause": frame.debug_summary.root_cause,
            "fix_priority": frame.debug_summary.fix_priority,
        },
        "keyword_audit": {
            "matched_in_answer": kw_in_answer,
            "matched_in_evidence": kw_in_evidence,
            "missed": kw_misses,
        },
        "telemetry_frame": frame.to_dict(),
    }
    trace_path = failures_dir / f"{q_id}_failure_trace.json"
    try:
        trace_path.write_text(json.dumps(trace_payload, indent=2), encoding="utf-8")
        print(f"   {C.DANGER}📁 Forensic Trace Exported:{C.RESET} {sanitize_path(trace_path)}")
    except Exception as ex:
        print(f"   {C.MUTED}Failed to export failure trace: {ex}{C.RESET}")


def render_benchmark_summary_card(
    results_summary: List[Dict[str, Any]],
    total_q: int,
    total_suite_time: float,
    suite_title: str,
) -> None:
    """Renders final comprehensive target metrics forensic scorecard."""
    passes = sum(1 for r in results_summary if r["strict_correct"])
    mean_hop = sum(r["hop_recall"] for r in results_summary) / total_q
    mean_bridge = sum(r["bridge_recall"] for r in results_summary) / total_q
    mean_ev_cov = sum(r["evidence_coverage"] for r in results_summary) / total_q
    mean_ctx_prec = sum(r["context_precision"] for r in results_summary) / total_q
    mean_entity = sum(r["entity_res_acc"] for r in results_summary) / total_q
    mean_table = sum(r["table_acc"] for r in results_summary) / total_q
    mean_temporal = sum(r["temporal_acc"] for r in results_summary) / total_q
    mean_numerical = sum(r["numerical_acc"] for r in results_summary) / total_q
    tot_correct_abst = sum(r["correct_abstention"] for r in results_summary)
    tot_recov_abst = sum(r["recoverable_abstention"] for r in results_summary)

    print("\n" + C.BANNER + "╔" + "═" * 76 + "╗" + C.RESET)
    print(f"  {C.BANNER}║{C.RESET} {C.TITLE}COMPREHENSIVE TARGET METRICS FORENSIC SCORECARD{C.RESET}{' ' * max(0, (28 - len(suite_title[:20])))} {C.BANNER}║{C.RESET}")
    print("  " + C.BANNER + "╠" + "═" * 76 + "╣" + C.RESET)
    print(f"  {C.BANNER}║{C.RESET}  Total Questions Evaluated       : {C.NUM}{total_q:<4}{C.RESET} ({total_suite_time}s total time)                 {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Strict Correctness (Release OK) : {C.SUCCESS if passes else C.DANGER}{passes:<4}{C.RESET} ({(passes/total_q)*100.0:>5.1f}%)                                {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Hop Recall (Found All Steps)    : {C.NUM}{mean_hop:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Bridge Recall (Neo4j Connected) : {C.NUM}{mean_bridge:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Evidence Coverage (Pre-synth)   : {C.NUM}{mean_ev_cov:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Context Precision (Cited/Packed): {C.NUM}{mean_ctx_prec:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Entity Resolution Accuracy      : {C.NUM}{mean_entity:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Table Extraction Accuracy       : {C.NUM}{mean_table:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Temporal Comparison Accuracy    : {C.NUM}{mean_temporal:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Numerical Calculation Accuracy  : {C.NUM}{mean_numerical:>5.1f} %{C.RESET}                                            {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Correct Abstention Rate (Safety): {C.SUCCESS}{int(tot_correct_abst):<4}{C.RESET} questions                                    {C.BANNER}║{C.RESET}")
    print(f"  {C.BANNER}║{C.RESET}  Recoverable Abstentions (Headrm): {C.WARN if tot_recov_abst else C.MUTED}{int(tot_recov_abst):<4}{C.RESET} questions (OCR / Missed Retrieval)      {C.BANNER}║{C.RESET}")
    print("  " + C.BANNER + "╠" + "═" * 76 + "╣" + C.RESET)
    print(f"  {C.BANNER}║{C.RESET}  {'ID':<5} │ {'T':<2} │ {'Status':<8} │ {'Hop%':<5} │ {'Brdg%':<5} │ {'EvCov':<5} │ {'Num%':<5} │ {'Failure Class':<19} {C.BANNER}║{C.RESET}")
    print("  " + C.BANNER + "╟" + "─" * 76 + "╢" + C.RESET)
    for r in results_summary:
        st_color = C.SUCCESS if r["strict_correct"] else (C.DANGER if r["status"] == "BLOCKED" else C.WARN)
        f_class = r["failure_class"][:19]
        print(f"  {C.BANNER}║{C.RESET}  {r['q_id']:<5} │ {r['tier']:<2} │ {st_color}{r['status']:<8}{C.RESET} │ {r['hop_recall']:>4.0f}% │ {r['bridge_recall']:>4.0f}% │ {r['evidence_coverage']:>4.0f}% │ {r['numerical_acc']:>4.0f}% │ {f_class:<19} {C.BANNER}║{C.RESET}")
    print("  " + C.BANNER + "╚" + "═" * 76 + "╝" + C.RESET + "\n")
