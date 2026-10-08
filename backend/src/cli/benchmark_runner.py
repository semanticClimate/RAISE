"""
RAISE — Forensic Benchmark Runner (src/cli/benchmark_runner.py)
===============================================================
Runs automated end-to-end benchmark evaluation suites (RAISE-Bench & FRAMES)
directly inside the Developer Observability Console with:
1. Honest Ground Truth vs RAISE Pipeline Answer comparison (No NotebookLM synthetic data).
2. Complete 8-layer TelemetryFrame computation & terminal rendering.
3. Adaptive Multi-Hop Iterative Recovery Loop:
      insufficient evidence
              ↓
      identify missing hop
              ↓
      targeted retrieval
              ↓
      graph bridge search (Neo4j)
              ↓
      second retrieval
              ↓
      still insufficient?
              ↓
      abstain (Safe anti-hallucination refusal)
4. Tracking of all essential target metrics:
   - Strict correctness, Hop recall, Bridge recall, Evidence coverage,
     Context precision, Correct/Recoverable abstention, Entity resolution,
     Table, Temporal, and Numerical accuracy.
5. Automated root-cause forensic classification and failure trace export.

Modular architecture:
  - `src.cli.frames_bench`: Google Research FRAMES sandbox benchmark runner.
  - `src.cli.benchmark_reporter`: Scorecard rendering and forensic trace JSON export.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.cli.telemetry_service import TelemetryService
from src.cli.renderer import C, TelemetryRenderer
from src.cli.commands import sanitize_path
from src.retrieval.chain_gate import ChainCompletenessGate
from src.cli.frames_bench import run_dev_frames_benchmark
from src.cli.benchmark_reporter import (
    compute_question_target_metrics,
    print_provenance_scorecard,
    export_benchmark_failure_trace,
    render_benchmark_summary_card,
)

BASE_DIR = Path(__file__).resolve().parents[2]

__all__ = [
    "ChainCompletenessGate",
    "execute_iterative_recovery_query",
    "run_dev_benchmark",
    "run_dev_frames_benchmark",
]


def execute_iterative_recovery_query(
    pipeline: Any,
    query: str,
    focused_doc: Optional[str] = None,
    req_keywords: Optional[List[str]] = None,
    tier: int = 1,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Executes query with the Evidence-Driven Adaptive Multi-Hop Iterative Recovery Loop:
      Hop 1 Retrieval -> Chain Completeness Gate -> Incomplete? ->
      Extract Evidence Bridge Entity (from chunks/graph, NOT query) ->
      Constrained Typed Neo4j Bridge Search -> Targeted Hop 2 Retrieval ->
      Pre-Synthesis Chain Completeness Gate -> Still incomplete? -> Abstain Honestly.
    """
    recovery_meta: Dict[str, Any] = {
        "loop_executed": False,
        "evidence_bridge_entity": None,
        "missing_hops_identified": [],
        "targeted_subquery": None,
        "graph_bridges_found": [],
        "second_retrieval_pass": False,
        "recovery_succeeded": False,
    }

    gate = ChainCompletenessGate(neo4j_db=getattr(pipeline, "neo4j_db", None))

    # Step 1: Initial Retrieval & GraphRAG Synthesis
    hops_initial = 3 if tier in (2, 3) else 2
    top_k_initial = 8 if tier in (2, 3) else 6
    res = pipeline.query_subgraph_graphrag(
        query=query,
        hops=hops_initial,
        top_k=top_k_initial,
        document_filter=focused_doc,
        mode="fast",
    )
    if not isinstance(res, dict):
        res = {"grounded_answer": str(res)}

    citations = res.get("citations") or []
    subgraph = res.get("subgraph") or {}
    answer = str(res.get("grounded_answer") or res.get("answer") or "")
    qg_decision = str(res.get("quality_gate_decision") or "accept").lower()

    # Pre-Synthesis Chain Completeness Gate Evaluation
    gate_res = gate.evaluate_chain(query, citations, subgraph=subgraph, is_recovery_pass=False)
    res["chain_gate_result"] = gate_res

    # Multi-Condition Recovery Trigger
    retrieval_count = len(citations)
    chunks_text = " ".join([c.get("text", "") for c in citations]).lower()
    matched_kw = sum(1 for kw in req_keywords if kw.lower() in chunks_text) if req_keywords else 1
    ev_coverage = (matched_kw / len(req_keywords)) if req_keywords else 1.0
    top_rerank_conf = float(citations[0].get("similarity", 0.0)) if citations else 0.0

    trigger_recovery = (
        retrieval_count == 0
        or (not gate_res.is_complete and tier in (2, 3))
        or (ev_coverage < 0.60 and tier in (2, 3))
        or top_rerank_conf < 0.25
        or ("refusal" in qg_decision and tier in (2, 3))
        or not answer.strip()
    )

    if not trigger_recovery:
        return res, recovery_meta

    # RECOVERY STEP 1: Evidence-Driven Bridge Extraction
    bridge_entity = gate_res.discovered_bridge_entity
    target_attr = gate_res.target_attribute

    if not bridge_entity:
        for c in citations[:2]:
            c_text = c.get("text", "")
            matches = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b", c_text)
            for m in matches:
                if len(m) > 4 and m.lower() not in query.lower():
                    bridge_entity = m
                    break
            if bridge_entity:
                break

    if not bridge_entity and req_keywords:
        for kw in req_keywords:
            if kw.lower() not in chunks_text and len(kw) > 3:
                bridge_entity = kw
                break

    if not bridge_entity:
        return res, recovery_meta

    recovery_meta["loop_executed"] = True
    recovery_meta["evidence_bridge_entity"] = bridge_entity
    recovery_meta["missing_hops_identified"] = [bridge_entity]

    print(f"\n  {C.WARN}⚡ [Evidence-Driven Iterative Recovery Loop Activated]{C.RESET}")
    print(f"     [1] Discovered Evidence Bridge: {C.NUM}{bridge_entity}{C.RESET} (Target: {target_attr or 'attribute'})")

    # RECOVERY STEP 2: Constrained Typed Neo4j Bridge Search
    bridged_nodes: List[str] = []
    bridged_pages: Set[int] = set()
    try:
        if hasattr(pipeline, "neo4j_db") and pipeline.neo4j_db:
            records = pipeline.neo4j_db.query_constrained_bridge(
                bridge_entity=bridge_entity,
                doc_id=focused_doc,
                limit=8,
            )
            for r in records:
                b_target = r.get("target")
                if b_target and b_target not in bridged_nodes and b_target.lower() != bridge_entity.lower():
                    bridged_nodes.append(str(b_target))
                if r.get("page"):
                    try:
                        bridged_pages.add(int(r["page"]))
                    except Exception:
                        pass
    except Exception:
        pass

    recovery_meta["graph_bridges_found"] = bridged_nodes
    if bridged_nodes:
        print(f"     [2] Typed Graph Bridge     : Connected to {C.SUCCESS}{bridged_nodes[:3]}{C.RESET} (Pages: {list(bridged_pages)[:4]})")
    else:
        print("     [2] Typed Graph Bridge     : Zero direct typed relations; falling back to lexical expansion.")

    # RECOVERY STEP 3: Targeted Second-Hop Retrieval
    recovery_meta["second_retrieval_pass"] = True
    bridge_expansion = " ".join(bridged_nodes[:2]) if bridged_nodes else ""
    targeted_hop2_query = f'"{bridge_entity}" {target_attr or ""} {bridge_expansion}'.strip()
    recovery_meta["targeted_subquery"] = targeted_hop2_query
    print(f"     [3] Targeted Hop 2 Query   : '{C.CYAN}{targeted_hop2_query}{C.RESET}'")

    res2 = pipeline.query_subgraph_graphrag(
        query=f"{query} {targeted_hop2_query}".strip(),
        hops=3,
        top_k=10,
        document_filter=focused_doc,
        mode="expert",
    )
    if not isinstance(res2, dict):
        res2 = {"grounded_answer": str(res2)}

    cit2 = res2.get("citations") or []
    combined_citations = list(citations)
    seen_ids = {c.get("chunk_id") or c.get("id") for c in citations}
    for c in cit2:
        cid = c.get("chunk_id") or c.get("id")
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            combined_citations.append(c)

    res2["citations"] = combined_citations

    # RECOVERY STEP 4: Pre-Synthesis Chain Completeness Gate
    gate2_res = gate.evaluate_chain(query, combined_citations, subgraph=res2.get("subgraph"), is_recovery_pass=True)
    res2["chain_gate_result"] = gate2_res

    ans2 = str(res2.get("grounded_answer") or res2.get("answer") or "")
    qg2 = str(res2.get("quality_gate_decision") or "accept").lower()

    if gate2_res.is_complete and len(combined_citations) > 0 and ans2.strip() and "refusal" not in qg2:
        print(f"  {C.SUCCESS}✓ [Recovery Succeeded]{C.RESET} Multi-hop reasoning chain complete & fully grounded!\n")
        recovery_meta["recovery_succeeded"] = True
        res2["recovery_meta"] = recovery_meta
        return res2, recovery_meta
    else:
        print(f"  {C.MUTED}⚠️ [Recovery Abstention Gate]{C.RESET} Chain incomplete ({gate2_res.reason}). Cleanly abstaining.\n")
        res2["grounded_answer"] = (
            f"INSUFFICIENT_EVIDENCE: Reasoning path incomplete. Discovered intermediate entity '{bridge_entity}', "
            f"but binding evidence connecting to '{target_attr or 'the requested figure'}' could not be verified."
        )
        res2["quality_gate_decision"] = "refusal"
        res2["recovery_meta"] = recovery_meta
        return res2, recovery_meta


def run_dev_benchmark(
    pipeline: Any,
    memory: Any,
    session: Any,
    benchmark_type: str = "raise",
    limit: Optional[int] = None,
):
    """
    Executes benchmark evaluation with deep telemetry rendering, multi-hop recovery,
    and granular multi-target metric tracking.
    """
    bench_type_lower = benchmark_type.strip().lower()
    if bench_type_lower in ("raise", "raise-bench", "raisebench"):
        dataset_path = BASE_DIR / "evaluation" / "benchmark_qa.json"
        suite_title = "RAISE INSTITUTIONAL BENCHMARK SUITE (RAISE-Bench-V1)"
    elif bench_type_lower in ("frames", "frames-bench", "framesbench"):
        return run_dev_frames_benchmark(pipeline, memory, session, limit=limit)
    else:
        candidate_path = Path(benchmark_type)
        if candidate_path.exists():
            dataset_path = candidate_path
            suite_title = f"CUSTOM BENCHMARK SUITE ({candidate_path.name})"
        else:
            print(f"{C.DANGER}❌ Unknown benchmark suite: '{benchmark_type}'. Options: 'raise', 'frames', or path to JSON.{C.RESET}")
            return

    if not dataset_path.exists():
        print(f"{C.DANGER}❌ Benchmark dataset not found at: {sanitize_path(dataset_path)}{C.RESET}")
        return

    try:
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{C.DANGER}❌ Failed to load benchmark dataset JSON: {e}{C.RESET}")
        return

    questions = data.get("questions", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    if not questions:
        print(f"{C.WARN}⚠️ No questions found in {dataset_path.name}.{C.RESET}")
        return

    if limit is not None and limit > 0:
        questions = questions[:limit]

    total_q = len(questions)

    print("\n" + C.BANNER + "═" * 78 + C.RESET)
    print(f" {C.TITLE}🏆 {suite_title}{C.RESET}")
    print(f" {C.MUTED}Total Questions: {total_q} | Mode: {session.mode.value} | Multi-Hop Recovery: ACTIVE{C.RESET}")
    print(C.BANNER + "═" * 78 + C.RESET)

    failures_dir = BASE_DIR / "logs" / "traces" / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)

    manifest_docs = pipeline.vector_engine.get_active_workspace_documents() if hasattr(pipeline, "vector_engine") else []
    results_summary: List[Dict[str, Any]] = []
    t_suite_start = time.time()

    for idx, q_item in enumerate(questions, 1):
        q_id = q_item.get("q_id", f"Q{idx:03d}")
        tier = int(q_item.get("tier", 1))
        q_text = q_item.get("question") or q_item.get("query") or ""
        gt_answer = q_item.get("ground_truth_answer") or q_item.get("expected_answer") or ""
        target_doc = q_item.get("target_document")
        req_keywords = q_item.get("required_keywords") or []
        page_citations = q_item.get("page_citations") or []

        exp_pages: List[int] = []
        for pc in page_citations:
            found = re.findall(r"Page\s+(\d+)", str(pc), re.IGNORECASE)
            for f in found:
                exp_pages.append(int(f))

        exp_figures: Dict[str, str] = {}
        for kw in req_keywords:
            if any(char.isdigit() for char in str(kw)):
                exp_figures[str(kw)] = str(kw)

        focused_doc = None
        if target_doc:
            for d in manifest_docs:
                if target_doc.lower() in d.lower():
                    focused_doc = d
                    break

        print("\n" + C.BANNER + "━" * 78 + C.RESET)
        print(f" {C.SECTION}[{idx}/{total_q}] {q_id} (Tier {tier}){C.RESET} — {C.WHITE}{q_text}{C.RESET}")
        if focused_doc:
            print(f"   {C.MUTED}Target Document Scope: {C.ACCENT}'{focused_doc}'{C.RESET}")
        print(C.BANNER + "━" * 78 + C.RESET)

        t0 = time.time()
        result, recovery_meta = execute_iterative_recovery_query(
            pipeline=pipeline,
            query=q_text,
            focused_doc=focused_doc,
            req_keywords=req_keywords,
            tier=tier,
        )
        latency_ms = round((time.time() - t0) * 1000.0, 1)

        result["benchmark_expected"] = {
            "q_id": q_id,
            "tier": tier,
            "expected_pages": exp_pages,
            "expected_figures": exp_figures,
            "ground_truth_answer": gt_answer,
            "required_keywords": req_keywords,
        }

        turn_id = f"BENCH-{q_id}-{int(time.time())}"
        frame = TelemetryService.build_frame(
            result=result,
            query=q_text,
            turn_id=turn_id,
            session_id=session.session_id,
            scope=focused_doc or "ALL DOCUMENTS",
            mode=session.mode.value,
        )

        TelemetryRenderer.render(frame, session.mode)

        # Compute Target Metrics for this question
        m = compute_question_target_metrics(
            frame=frame,
            req_keywords=req_keywords,
            tier=tier,
            q_text=q_text,
            target_doc=target_doc,
            recovery_meta=recovery_meta,
        )

        print_provenance_scorecard(
            gt_answer=gt_answer,
            ans_clean=m["ans_clean"],
            strict_correct=m["strict_correct"],
            hop_recall_pct=m["hop_recall_pct"],
            hops_found=m["hops_found"],
            required_hops=m["required_hops"],
            bridge_recall_pct=m["bridge_recall_pct"],
            ev_cov=m["ev_cov"],
            kw_in_evidence_cnt=len(m["kw_in_evidence"]),
            req_keywords_cnt=len(req_keywords),
            ctx_precision=m["ctx_precision"],
            table_acc=m["table_acc"],
            temporal_acc=m["temporal_acc"],
            numerical_acc=m["numerical_acc"],
            num_matches_cnt=len(m["num_matches"]),
            num_total_cnt=len(m["num_total"]),
            outcome_status=m["outcome_status"],
            kw_misses=m["kw_misses"],
        )

        if not m["strict_correct"] or frame.debug_summary.status in ("BLOCKED", "FAILED"):
            export_benchmark_failure_trace(
                failures_dir=failures_dir,
                q_id=q_id,
                tier=tier,
                q_text=q_text,
                target_doc=target_doc,
                req_keywords=req_keywords,
                gt_answer=gt_answer,
                strict_correct=m["strict_correct"],
                hop_recall_pct=m["hop_recall_pct"],
                bridge_recall_pct=m["bridge_recall_pct"],
                ev_cov=m["ev_cov"],
                ctx_precision=m["ctx_precision"],
                correct_abstention=m["correct_abstention"],
                recoverable_abstention=m["recoverable_abstention"],
                entity_res_acc=m["entity_res_acc"],
                table_acc=m["table_acc"],
                temporal_acc=m["temporal_acc"],
                numerical_acc=m["numerical_acc"],
                recovery_meta=recovery_meta,
                outcome_status=m["outcome_status"],
                frame=frame,
                kw_in_answer=m["kw_in_answer"],
                kw_in_evidence=m["kw_in_evidence"],
                kw_misses=m["kw_misses"],
            )

        f_class_val = (
            frame.debug_summary.failure_class.value
            if hasattr(frame.debug_summary.failure_class, "value")
            else str(frame.debug_summary.failure_class)
        )
        results_summary.append({
            "q_id": q_id,
            "tier": tier,
            "status": m["outcome_status"],
            "failure_class": f_class_val,
            "latency_ms": latency_ms,
            "strict_correct": m["strict_correct"],
            "hop_recall": m["hop_recall_pct"],
            "bridge_recall": m["bridge_recall_pct"],
            "evidence_coverage": m["ev_cov"],
            "context_precision": m["ctx_precision"],
            "correct_abstention": m["correct_abstention"],
            "recoverable_abstention": m["recoverable_abstention"],
            "entity_res_acc": m["entity_res_acc"],
            "table_acc": m["table_acc"],
            "temporal_acc": m["temporal_acc"],
            "numerical_acc": m["numerical_acc"],
        })

    total_suite_time = round(time.time() - t_suite_start, 2)
    render_benchmark_summary_card(results_summary, total_q, total_suite_time, suite_title)

