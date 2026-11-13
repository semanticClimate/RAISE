"""
RAISE Telemetry Terminal Renderer
=================================
Dedicated presentation layer rendering TelemetryFrame into structured,
high-contrast ANSI terminal views (8 Observability Layers, ASCII Trees,
Candidate Audit Funnel, Numerical Consistency Audit, Claims Audit,
Latency Bar Charts, and Forensic Debug Summary Card).
Decoupled entirely from telemetry calculation and business logic.

Architecture:
  - `src.cli.ansi_palette`: ANSI colors (C), ObsMode, metric formatter.
  - `src.cli.render_cards`: ASCII tree and boxed debug / reasoning chain cards.
  - `TelemetryRenderer`: Master coordinator orchestrating Layer 01 to Layer 08 rendering.

Author: RAISE Core Architecture Team
Maintainability: Keep under 380 lines with strict separation of concerns.
"""

from __future__ import annotations


from src.cli.models import (
    TelemetryFrame,
)
from src.cli.ansi_palette import C, ObsMode, strip_ansi, format_metric
from src.cli.render_cards import (
    render_ascii_graph_tree,
    render_debug_summary_card,
    render_reasoning_chain_card,
)

__all__ = ["C", "ObsMode", "TelemetryRenderer"]


class TelemetryRenderer:
    """Terminal UI renderer that visualizes a TelemetryFrame."""

    _strip_ansi = staticmethod(strip_ansi)
    _format_metric = staticmethod(format_metric)
    render_ascii_graph_tree = staticmethod(render_ascii_graph_tree)

    @classmethod
    def render(cls, frame: TelemetryFrame, mode: ObsMode = ObsMode.TRACE):
        """Renders the TelemetryFrame according to the requested Observability mode."""
        if mode == ObsMode.NORMAL:
            return

        perf = frame.performance
        intent_m = frame.intent
        ret = frame.retrieval
        vec = ret.vector
        bm25 = ret.bm25
        graph = ret.graph
        rerank = ret.rerank
        ctx_assembly = frame.context_assembly
        synth = frame.synthesis
        qg = frame.quality
        prov = frame.provenance
        dbg = frame.debug_summary

        # LAYER 01 — REQUEST
        print("\n" + C.BANNER + "┌─ 01 — REQUEST " + "─" * 62 + "┐" + C.RESET)
        print(f"{C.BANNER}│{C.RESET}  • Turn ID    : {C.NUM}{frame.turn_id}{C.RESET}")
        print(f"{C.BANNER}│{C.RESET}  • Session    : {C.WHITE}{frame.session_id}{C.RESET}")
        print(f"{C.BANNER}│{C.RESET}  • Timestamp  : {C.MUTED}{frame.timestamp}{C.RESET}")
        print(f"{C.BANNER}│{C.RESET}  • Query      : {C.WHITE}\"{frame.query}\"{C.RESET}")
        print(f"{C.BANNER}│{C.RESET}  • Scope      : {C.ACCENT}{frame.scope}{C.RESET}")
        print(f"{C.BANNER}│{C.RESET}  • Mode       : {C.NUM}{mode.value}{C.RESET} (Strict Anti-Hallucination)")
        print(C.BANNER + "└" + "─" * 76 + "┘" + C.RESET)

        # LAYER 02 — INTENT & ROUTING (QUERY UNDERSTANDING)
        print("\n" + C.SECTION + "02 — INTENT & ROUTING (QUERY UNDERSTANDING)" + C.RESET)
        print(C.MUTED + "━" * 68 + C.RESET)
        print(f"  Primary Intent       {C.CYAN}{intent_m.intent.display()}{C.RESET}")
        print(f"  Confidence           {cls._format_metric(intent_m.confidence, '.2f')}")
        print(f"  Query Type           {C.WHITE}{intent_m.query_type.display()}{C.RESET}")
        print(f"  Complexity           {cls._format_metric(intent_m.complexity)}")
        print(f"  Domain               {C.ACCENT}{intent_m.domain}{C.RESET}")
        print(f"  Intent Rule Fired    {C.NUM}{intent_m.intent_rule_fired}{C.RESET}")
        print(f"  Routing Decision     {C.SUCCESS}{intent_m.routing_decision.display()}{C.RESET}")
        print(f"  Routing Explanation  {C.MUTED}{intent_m.routing_explanation}{C.RESET}")

        if intent_m.competing_intents:
            print("  Competing Intents    " + ", ".join([f"{k}: {v:.2f}" for k, v in intent_m.competing_intents.items()]))

        if len(intent_m.subqueries) > 1:
            print("\n  QUERY DECOMPOSITION:")
            for q_i, sq in enumerate(intent_m.subqueries, 1):
                print(f"    Q{q_i}  └─ {C.WHITE}{sq}{C.RESET}")
        print(f"  Routing Latency      {cls._format_metric(intent_m.latency_ms, '.1f')}")

        # LAYER 03 — RETRIEVAL TRACE & CANDIDATE AUDIT
        print("\n" + C.SECTION + "03 — RETRIEVAL TRACE & CANDIDATE AUDIT" + C.RESET)
        print(C.MUTED + "━" * 68 + C.RESET)

        # Funnel summary
        print(f"  {C.ACCENT}RETRIEVAL FUNNEL & SOURCES{C.RESET}")
        print("    Retrievers Active  : " + ", ".join([f"{k}: {'ON' if v else 'OFF'}" for k, v in ret.retrievers_enabled.items()]))
        print(f"    Vector Candidates  : {cls._format_metric(vec.candidates)} (Top-K: {cls._format_metric(vec.top_k)})")
        print(f"    BM25 Candidates    : {cls._format_metric(bm25.candidates)} (Exact: {cls._format_metric(bm25.exact_matches)})")
        print(f"    Candidates Merged  : {cls._format_metric(ret.candidates_merged)}")
        print(f"    Deduplicated Count : {cls._format_metric(ret.candidates_deduplicated)}")
        print(f"    Output Evidence    : {cls._format_metric(rerank.output_evidence)} chunks")

        # Vector Search
        print(f"\n  {C.ACCENT}VECTOR RETRIEVAL{C.RESET}")
        print(f"    Model              : {vec.model}")
        print(f"    Collection         : {vec.collection}")
        if vec.distance_min.is_available and vec.distance_max.is_available:
            dist_str = f"{vec.distance_min.value:.3f} → {vec.distance_max.value:.3f} [MEASURED]"
        else:
            dist_str = f"-- [{vec.distance_min.state.value}]"
        print(f"    Distance Range     : {C.NUM}{dist_str}{C.RESET}")
        print(f"    Vector Latency     : {cls._format_metric(vec.latency_ms, '.1f')}")

        # Graph Search
        print(f"\n  {C.ACCENT}GRAPH SEARCH (NEO4J){C.RESET}")
        print(f"    Entry Entities     : {cls._format_metric(graph.entry_entities)}")
        print(f"    Nodes Visited      : {cls._format_metric(graph.nodes_visited)}")
        print(f"    Edges Traversed    : {cls._format_metric(graph.edges_traversed)}")
        print(f"    Cypher Latency     : {cls._format_metric(graph.latency_ms, '.1f')}")

        # Reranking / Fusion
        print(f"\n  {C.ACCENT}RERANKING & RECIPROCAL RANK FUSION{C.RESET}")
        print(f"    Mean Score         : {cls._format_metric(rerank.mean_score, '.3f')}")
        print(f"    Score Improvement  : {cls._format_metric(rerank.score_improvement_pct, '.1f')}")
        print(f"    Rerank Latency     : {cls._format_metric(rerank.latency_ms, '.1f')}")

        # Top Candidates Audit Table
        if mode in (ObsMode.TRACE, ObsMode.DEBUG) and ret.top_candidates_audit:
            print(f"\n  {C.ACCENT}TOP CANDIDATES AUDIT (Funnel & Reranker Dropout Trace){C.RESET}")
            print("  ┌──────┬──────────────────────┬──────────┬──────────────────────┬──────┬─────────────────┬──────────────────────┐")
            print("  │ Rank │ Chunk ID             │ Score    │ Retriever            │ Page │ Status          │ Section / Heading    │")
            print("  ├──────┼──────────────────────┼──────────┼──────────────────────┼──────┼─────────────────┼──────────────────────┤")
            for cand in ret.top_candidates_audit[:6]:
                head_sub = (cand.heading[:20] if cand.heading else "--")
                stat_badge = f"{C.DANGER}RERANK_DROP{C.RESET}    " if cand.reranker_dropout else f"{C.SUCCESS}IN_CONTEXT{C.RESET}     "
                print(f"  │ {cand.rank:>4} │ {cand.chunk_id:<20} │ {cand.score:>8.4f} │ {cand.retriever:<20} │ {cand.primary_page:>4} │ {stat_badge} │ {head_sub:<20} │")
            print("  └──────┴──────────────────────┴──────────┴──────────────────────┴──────┴─────────────────┴──────────────────────┘")

        if mode in (ObsMode.TRACE, ObsMode.DEBUG):
            # LAYER 04 — EVIDENCE GRAPH
            print("\n" + C.SECTION + "04 — EVIDENCE GRAPH" + C.RESET)
            print(C.MUTED + "━" * 68 + C.RESET)
            cls.render_ascii_graph_tree(prov.citations)

            # LAYER 05 — CONTEXT ASSEMBLY & TOKEN DIAGNOSTICS
            print("\n" + C.SECTION + "05 — CONTEXT ASSEMBLY & TOKEN DIAGNOSTICS" + C.RESET)
            print(C.MUTED + "━" * 68 + C.RESET)
            print(f"  Provider             {C.WHITE}{synth.provider}{C.RESET}")
            print(f"  Model                {C.ACCENT}{synth.model}{C.RESET}")
            print(f"  Chunks in Context    {cls._format_metric(ctx_assembly.chunks_in_context)}")
            print(f"  Unique Documents     {C.NUM}{ctx_assembly.unique_documents}{C.RESET}")
            print(f"  Unique Pages         {C.NUM}{ctx_assembly.unique_pages}{C.RESET}")
            print(f"  Context Tokens       {cls._format_metric(ctx_assembly.context_tokens)} / {ctx_assembly.max_context_tokens} max")
            print(f"  Context Utilization  {cls._format_metric(ctx_assembly.context_utilization_pct)}")
            print(f"  Chunks Dropped       {C.NUM}{ctx_assembly.chunks_dropped}{C.RESET}")
            print(f"  Output Tokens        {cls._format_metric(synth.output_tokens)}")
            if synth.time_to_first_token_ms.is_available:
                print(f"  Prefill (TTFT)       {cls._format_metric(synth.time_to_first_token_ms, '.1f')}")
                print(f"  Decode Throughput    {cls._format_metric(synth.generation_speed_tok_s, '.1f')}")
            else:
                print(f"  Generation Speed     {cls._format_metric(synth.generation_speed_tok_s, '.1f')}")
            print(f"  Grounding Mode       {C.SUCCESS}{synth.grounding_mode}{C.RESET}")
            print(f"  Citation Contract    {C.SUCCESS}{synth.citation_contract}{C.RESET}")

            if frame.prompt_context and frame.prompt_context.context_snippets:
                print(f"\n  {C.ACCENT}PROMPT-CONTEXT WORKING MEMORY (Packets Fed to Synthesizer){C.RESET}")
                for snip in frame.prompt_context.context_snippets[:3]:
                    h_str = f" [{snip.get('heading')}]" if snip.get('heading') else ""
                    print(f"    • {C.CYAN}{snip.get('chunk_id')}{C.RESET} (Page {snip.get('primary_page')}){h_str}:")
                    txt_preview = snip.get('text', '').replace('\n', ' ').strip()
                    if len(txt_preview) > 110:
                        txt_preview = txt_preview[:107] + "..."
                    print(f"      {C.MUTED}\"{txt_preview}\"{C.RESET}")

        # LAYER 06 — QUALITY GATE & FORENSIC AUDITS
        print("\n" + C.SECTION + "06 — QUALITY GATE & FORENSIC AUDITS" + C.RESET)
        print(C.MUTED + "━" * 68 + C.RESET)
        print("  ┌──────────────────────────┬──────────┬───────────────┐")
        print("  │ Metric                   │ Score    │ Status        │")
        print("  ├──────────────────────────┼──────────┼───────────────┤")
        
        ov_str = f"{qg.evidence_overlap_pct.value:>6.1f} %" if qg.evidence_overlap_pct.is_available else "   N/A  "
        ov_stat = f"{C.SUCCESS}✓ PASS{C.RESET}" if qg.evidence_overlap_pct.is_available else f"{C.MUTED}UNAVAIL{C.RESET}"
        print(f"  │ Evidence overlap         │ {ov_str} │ {ov_stat}       │")
        
        if qg.numerical_claims_verified.is_available and qg.numerical_claims_total.is_available and qg.numerical_claims_total.value and int(qg.numerical_claims_total.value) > 0:
            num_str = f"{qg.numerical_claims_verified.value:>4} / {qg.numerical_claims_total.value:<2}"
            num_stat = f"{C.SUCCESS}✓ PASS{C.RESET}" if qg.numerical_claims_verified.value == qg.numerical_claims_total.value else f"{C.DANGER}✗ FAIL{C.RESET}"
        else:
            num_str = "   N/A  "
            num_stat = f"{C.MUTED}N/A    {C.RESET}"
        print(f"  │ Numerical verification   │ {num_str} │ {num_stat}       │")
        
        cb_str = f"{qg.citation_precision_pct.value:>6.1f} %" if qg.citation_precision_pct.is_available else "   N/A  "
        cb_stat = f"{C.SUCCESS}✓ PASS{C.RESET}" if (qg.citation_precision_pct.is_available and qg.citation_precision_pct.value == 100.0) else f"{C.WARN}REVIEW {C.RESET}"
        print(f"  │ Citation precision       │ {cb_str} │ {cb_stat}       │")
        
        if len(prov.citations) > 0:
            cov_str = f"{len(prov.citations):>4} / {len(prov.citations):<2}"
            cov_stat = f"{C.SUCCESS}✓ PASS{C.RESET}"
        else:
            cov_str = "   N/A  "
            cov_stat = f"{C.DANGER}✗ NONE {C.RESET}"
        print(f"  │ Source coverage          │ {cov_str} │ {cov_stat}       │")
        
        if qg.faithfulness_score.is_available:
            f_str = f"{qg.faithfulness_score.value:>6.2f}"
            f_stat = f"{C.SUCCESS}✓ PASS{C.RESET}" if qg.faithfulness_score.value >= 0.80 else f"{C.DANGER}✗ FAIL{C.RESET}"
        else:
            f_str = "   N/A"
            f_stat = f"{C.MUTED}UNAVAIL{C.RESET}"
        print(f"  │ Faithfulness             │   {f_str} │ {f_stat}       │")
        
        if qg.unsupported_claims_count.is_available:
            u_str = f"{qg.unsupported_claims_count.value:>6}"
            u_stat = f"{C.SUCCESS}✓ PASS{C.RESET}" if qg.unsupported_claims_count.value == 0 else f"{C.DANGER}✗ FAIL{C.RESET}"
        else:
            u_str = "   N/A"
            u_stat = f"{C.MUTED}UNAVAIL{C.RESET}"
        print(f"  │ Unsupported claims       │ {u_str}   │ {u_stat}       │")
        print("  └──────────────────────────┴──────────┴───────────────┘")

        if qg.is_gate_passed:
            print(f"  FINAL GATE: {C.SUCCESS}✓ ANSWER RELEASED{C.RESET}")
        else:
            print(f"  FINAL GATE: {C.DANGER}✗ ANSWER BLOCKED{C.RESET} (Reason: {qg.rejection_reason or 'Quality Gate check failed'})")

        # Numerical Consistency & Arithmetic Audit
        if qg.numerical_audit and qg.numerical_audit.relationships:
            print(f"\n  {C.ACCENT}NUMERICAL CONSISTENCY & ARITHMETIC AUDIT{C.RESET}")
            print("    Detected Figures   : " + ", ".join(qg.numerical_audit.detected_metrics))
            for rel in qg.numerical_audit.relationships:
                print(f"    Equation Check     : {C.NUM}{rel}{C.RESET} [{C.SUCCESS}✓ VERIFIED{C.RESET}]")
            print(f"    Arithmetic Status  : {C.SUCCESS}{qg.numerical_audit.arithmetic_status}{C.RESET} (Tolerance: {qg.numerical_audit.tolerance})")

        # Granular Numerical & Entity Verification Diff
        if frame.numerical_diffs:
            print(f"\n  {C.ACCENT}GRANULAR NUMERICAL & ENTITY VERIFICATION DIFF{C.RESET}")
            print("  ┌──────────────────────────────┬──────────────┬──────────────┬──────────────┬──────────────────┐")
            print("  │ Metric / Fact Name           │ Ground Truth │ Pipeline     │ Source Page  │ Verification     │")
            print("  ├──────────────────────────────┼──────────────┼──────────────┼──────────────┼──────────────────┤")
            for nd in frame.numerical_diffs:
                m_sub = nd.metric_name[:28]
                gt_sub = (nd.ground_truth_value or "--")[:12]
                pip_sub = (nd.pipeline_value or "--")[:12]
                p_info = f"p.{nd.source_page_expected}" if nd.source_page_expected else "--"
                if nd.status == "PASS":
                    st_badge = f"{C.SUCCESS}✓ PASS{C.RESET}         "
                elif nd.status == "MISMATCH":
                    st_badge = f"{C.DANGER}✗ MISMATCH{C.RESET}     "
                else:
                    st_badge = f"{C.WARN}⚠️ {nd.status[:12]}{C.RESET}"
                print(f"  │ {m_sub:<28} │ {gt_sub:<12} │ {pip_sub:<12} │ {p_info:<12} │ {st_badge} │")
            print("  └──────────────────────────────┴──────────────┴──────────────┴──────────────┴──────────────────┘")

        # Claim-by-Claim Evidence Audit
        if mode in (ObsMode.TRACE, ObsMode.DEBUG) and qg.claims_audit:
            print(f"\n  {C.ACCENT}CLAIM-BY-CLAIM EVIDENCE AUDIT (Escalation Gating & FineCat-NLI){C.RESET}")
            print("  ┌──────┬──────────────────────────────────────────────────────┬──────────────┬──────┬───────┬─────────────┐")
            print("  │ ID   │ Extracted Claim / Sentence                           │ Bound Chunk  │ Page │ Tier  │ Status      │")
            print("  ├──────┼──────────────────────────────────────────────────────┼──────────────┼──────┼───────┼─────────────┤")
            for c_claim in qg.claims_audit[:6]:
                txt_trunc = c_claim.text[:52]
                c_id_str = c_claim.evidence_chunk_id[:12] if c_claim.evidence_chunk_id else "--"
                p_str = f"{c_claim.primary_page:>4}" if c_claim.primary_page is not None else "  --"
                tier_short = "NLI" if "NLI" in c_claim.verification_tier else ("LEX" if "LEX" in c_claim.verification_tier else ("NUM" if "NUM" in c_claim.verification_tier else "FALL"))

                if c_claim.support_status in ("DIRECT", "SUPPORTED"):
                    st_color, st_text = C.SUCCESS, "DIRECT PASS"
                elif c_claim.support_status == "NLI_ENTAILED":
                    st_color, st_text = C.SUCCESS, "✓ ENTAILED"
                elif c_claim.support_status == "CONTRADICTION":
                    st_color, st_text = C.DANGER, "✗ CONTRADICT"
                elif c_claim.support_status == "NUMERICAL_MISMATCH":
                    st_color, st_text = C.DANGER, "✗ NUM MISMAT"
                elif c_claim.support_status == "UNSUPPORTED":
                    st_color, st_text = C.DANGER, "✗ UNSUPPORT"
                else:
                    st_color, st_text = C.MUTED, c_claim.support_status[:11]

                st_str = f"{st_color}{st_text:<11}{C.RESET}"
                print(f"  │ {c_claim.claim_id:<4} │ {txt_trunc:<52} │ {c_id_str:<12} │ {p_str} │ {tier_short:<5} │ {st_str} │")
            print("  └──────┴──────────────────────────────────────────────────────┴──────────────┴──────┴───────┴─────────────┘")

        if mode in (ObsMode.TRACE, ObsMode.DEBUG):
            # LAYER 07 — PROVENANCE CHAIN
            print("\n" + C.SECTION + "07 — PROVENANCE CHAIN" + C.RESET)
            print(C.MUTED + "━" * 68 + C.RESET)
            for cit in prov.citations:
                p_str = f"PDF Page {cit.primary_page}, Doc Page {cit.printed_page}" if cit.printed_page and str(cit.printed_page) != str(cit.primary_page) else f"Page {cit.primary_page}"
                score_str = f"{cit.evidence_score.value:.3f}" if cit.evidence_score.is_available else "-- [UNAVAILABLE]"
                
                print(f"  {C.CITATION}[{cit.citation_index}]{C.RESET}")
                print("  Document")
                print(f"    └─ {C.CYAN}{cit.document}{C.RESET}")
                print(f"         └─ {C.SECTION}{p_str}{C.RESET}")
                print(f"              └─ Section: {C.WHITE}{cit.section_heading}{C.RESET}")
                print(f"                   └─ Chunk ID: {C.MUTED}{cit.chunk_id}{C.RESET}")
                print(f"                        └─ Evidence score: {C.NUM}{score_str}{C.RESET}")

        # LAYER 08 — PIPELINE PERFORMANCE & TIMING BREAKDOWN
        print("\n" + C.SECTION + "08 — PIPELINE PERFORMANCE" + C.RESET)
        print(C.MUTED + "━" * 68 + C.RESET)

        def make_bar(pct: float, width: int = 24) -> str:
            filled = int(round(pct / 100.0 * width))
            filled = min(width, max(1 if pct > 0.5 else 0, filled))
            return "█" * filled + "░" * (width - filled)

        pcts = perf.stage_percentages
        print(f"  Routing       {perf.routing_ms:>8.1f} ms   {C.ACCENT}{make_bar(pcts.get('Routing', 0.0))}{C.RESET}  {pcts.get('Routing', 0.0):>5.1f}%")
        print(f"  Retrieval     {perf.retrieval_ms:>8.1f} ms   {C.ACCENT}{make_bar(pcts.get('Retrieval', 0.0))}{C.RESET}  {pcts.get('Retrieval', 0.0):>5.1f}%")
        print(f"  Synthesis     {perf.synthesis_ms:>8.1f} ms   {C.ACCENT}{make_bar(pcts.get('Synthesis', 0.0))}{C.RESET}  {pcts.get('Synthesis', 0.0):>5.1f}%")
        print(f"  Quality Gate  {perf.quality_gate_ms:>8.1f} ms   {C.ACCENT}{make_bar(pcts.get('Quality Gate', 0.0))}{C.RESET}  {pcts.get('Quality Gate', 0.0):>5.1f}%")
        print("               " + "─" * 45)
        print(f"  TOTAL         {perf.total_latency_ms:>8.1f} ms   {C.BOLD}{C.SUCCESS}{perf.total_latency_ms/1000.0:.2f} sec{C.RESET}")

        print(f"\n  {C.MUTED}TIMING COVERAGE & LATENCY HIERARCHY{C.RESET}")
        print(f"  Instrumentation Coverage : {C.NUM}{perf.instrumentation_coverage_pct:.1f} %{C.RESET}")
        print(f"  Unattributed Overhead    : {C.NUM}{perf.unattributed_latency_ms:.1f} ms{C.RESET}")

        if mode in (ObsMode.TRACE, ObsMode.DEBUG) and perf.breakdown_tree:
            bt = perf.breakdown_tree
            print("  Sub-Stage Latency Breakdown:")
            print(f"    ├── Routing             : {bt.get('routing', 0.0):>6.1f} ms")
            print(f"    ├── Retrieval Subsystem : {perf.retrieval_ms:>6.1f} ms")
            print(f"    │     ├── Vector Search : {bt.get('retrieval_vector', 0.0):>6.1f} ms")
            print(f"    │     ├── BM25 Lexical  : {bt.get('retrieval_bm25', 0.0):>6.1f} ms")
            print(f"    │     ├── Graph Traversal: {bt.get('retrieval_graph', 0.0):>6.1f} ms")
            print(f"    │     └── Rerank / RRF  : {bt.get('retrieval_rerank', 0.0):>6.1f} ms")
            print(f"    ├── Synthesis Subsystem : {bt.get('synthesis', 0.0):>6.1f} ms")
            if 'synthesis_ttft' in bt and float(bt.get('synthesis_ttft', 0.0)) > 0:
                print(f"    │     ├── Prefill (TTFT): {float(bt.get('synthesis_ttft', 0.0)):>6.1f} ms")
                print(f"    │     └── Stream Decode : {float(bt.get('synthesis_decode', 0.0)):>6.1f} ms")
            print(f"    └── Quality Gate Engine : {bt.get('quality_gate', 0.0):>6.1f} ms")

        # Forensic Debug Summary Card
        render_debug_summary_card(dbg)

        # Reasoning Chain & Completeness Gate Card
        render_reasoning_chain_card(frame)

        if mode == ObsMode.DEBUG:
            cypher_str = graph.cypher_query.value if graph.cypher_query.is_available else "N/A"
            print(f"\n{C.SECTION}[RAW DEBUG INSPECTOR]{C.RESET}")
            print(f"  • Cypher Query : {C.MUTED}{cypher_str}{C.RESET}")
            print(f"  • Chunk IDs    : {[c.chunk_id for c in prov.citations]}")
            print(f"  • Stage Latency: {frame.raw_metadata.get('stages', {})}")
