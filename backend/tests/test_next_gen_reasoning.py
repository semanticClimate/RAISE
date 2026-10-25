"""
Next-Generation Retrieval, Graph, and Reasoning Regression Suite
Tests all failure classes and requirements from the 824-question forensic audit:
  - Sentence-initial entity extraction ("Did Krampus" bug)
  - Strict relation typing and incompatibility (HOSTED_BY vs WINNER)
  - Relational composition ("same scientist", "same year")
  - Deterministic calendar math and age calculations (Q25, Q45)
  - Derived answer proof-aware grounding without verbatim token presence (Q29 Harold Wilson)
  - Second-chance table resolution (row/col fallback)
  - Calibrated proof-driven abstention gating
"""

import pytest
from datetime import date

from src.graph.entity_resolver import EntityResolver
from src.graph.relation_resolver import RelationResolver, RelationType
from src.graph.proof_graph import ProofGraph, ProofHop, ProofEdge
from src.reasoning.query_planner import QueryPlanner, TypedQueryPlan
from src.reasoning.temporal import TemporalEngine
from src.reasoning.numerical import NumericalExecutor
from src.reasoning.surface_adapter import SurfaceConstraintAdapter
from src.reasoning.tables import TableReasoningEngine, ParsedTable
from src.reasoning.operators import UnifiedOperatorEngine
from src.retrieval.candidate_generation import CandidateGenerator
from src.retrieval.reranker import EvidenceReranker
from src.grounding.claim_graph import ClaimGraph, ProofType
from src.grounding.verifier import GroundingVerifier
from src.grounding.abstention import AbstentionGate, AbstentionDecision
try:
    from evaluation.archive.legacy_evaluation_scripts.benchmarks.frames.isolation.harness import IsolatedFramesHarness
except ImportError:
    IsolatedFramesHarness = None


# -----------------------------------------------------------------------------
# 1. Entity Resolver Tests: "Did X" Fix & Diacritics
# -----------------------------------------------------------------------------

def test_entity_resolver_sentence_initial_exclusion():
    """Verifies sentence-initial auxiliary verbs ('Did', 'What', 'Who') are never part of entity names."""
    resolver = EntityResolver()
    query = "Did Krampus defeat Goku in the tournament in 1988?"
    cands = resolver.extract_candidate_entities(query)
    
    assert "Did Krampus" not in cands
    assert "Krampus" in cands
    assert "Goku" in cands
    assert "1988" in cands


def test_entity_resolver_parenthetical_and_diacritics():
    """Verifies NFKD diacritic folding and parenthetical disambiguation."""
    resolver = EntityResolver()
    
    # Diacritic folding
    norm1 = resolver.normalize_entity("Lü Huihui")
    norm2 = resolver.normalize_entity("Lu Huihui")
    assert norm1 == norm2 == "lu huihui"
    assert resolver.normalize_entity("Atlético Madrid") == "atletico madrid"

    # Parenthetical strip
    base, qualifier = resolver.strip_parenthetical("Target House (London)")
    assert base == "Target House"
    assert qualifier == "London"
    
    # Resolution against known entities (including corrupted diacritics)
    known = {"Target House", "Geffen Records", "Lü Huihui"}
    match, conf = resolver.resolve("Target House (London)", known)
    assert match == "Target House"
    assert conf >= 0.95

    # Resolution of corrupted string to known entity
    match_corrupt, conf_corrupt = resolver.resolve("L\ufffd Huihui", known)
    assert match_corrupt == "Lü Huihui"
    assert conf >= 0.95


# -----------------------------------------------------------------------------
# 2. Relation Resolver Tests: Incompatibility & Vocabulary
# -----------------------------------------------------------------------------

def test_relation_resolver_winner_vs_host_incompatibility():
    """Fixes Q3/Russia vs France: WINNER and HOSTED_BY are strictly incompatible."""
    assert not RelationResolver.are_compatible(RelationType.WINNER, RelationType.HOSTED_BY)
    assert not RelationResolver.are_compatible(RelationType.HOSTED_BY, RelationType.WINNER)
    assert not RelationResolver.are_compatible(RelationType.CHAMPION, RelationType.HELD_IN)
    assert RelationResolver.are_compatible(RelationType.WINNER, RelationType.CHAMPION)


def test_relation_resolver_text_detection():
    """Detects relation types from natural text snippets."""
    text_winner = "France defeated Croatia 4-2 in the final to become World Champions."
    text_host = "The 2018 tournament was hosted by Russia across eleven cities."
    
    assert RelationResolver.detect_relation_from_text(text_winner) in (RelationType.WINNER, RelationType.CHAMPION)
    assert RelationResolver.detect_relation_from_text(text_host) == RelationType.HOSTED_BY


# -----------------------------------------------------------------------------
# 3. Query Planner Tests: Relational Composition ("Same Scientist")
# -----------------------------------------------------------------------------

def test_query_planner_relational_composition_same_scientist():
    """Fixes Q6: 'same scientist who discovered zirconium in the same year'."""
    planner = QueryPlanner()
    query = "Find the element whose atomic number is 9 greater than an element discovered by the same scientist who discovered zirconium in the same year."
    plan = planner.build_plan(query)
    
    assert plan.preserves_composition is True
    assert len(plan.hops) >= 3
    # Hop 1: Discoverer of Zirconium
    assert plan.hops[0].source_entity.lower() == "zirconium"
    assert plan.hops[0].required_relation == RelationType.DISCOVERED_BY
    # Hop 2: Same scientist, same year
    assert plan.hops[1].compositional_cue == "SAME_YEAR"
    # Operators: arithmetic +9
    assert any(op.type == "ADD" and op.parameters.get("delta") == 9.0 for op in plan.operators)


# -----------------------------------------------------------------------------
# 4. Temporal Engine Tests: Elapsed Full Years & Age
# -----------------------------------------------------------------------------

def test_temporal_engine_calendar_math_boundaries():
    """Fixes Q25 and Q45 calendar boundary arithmetic."""
    # Q25: Mike Tyson (June 30, 1966) vs Tyson Fury (August 12, 1988) -> Age Diff 22
    tyson = date(1966, 6, 30)
    fury = date(1988, 8, 12)
    diff = TemporalEngine.elapsed_full_years(tyson, fury)
    assert diff == 22

    # Stephen Baldwin (May 12, 1966) at Hailey/Justin Wedding (September 13, 2018) -> 52
    baldwin_birth = date(1966, 5, 12)
    wedding = date(2018, 9, 13)
    age = TemporalEngine.age_on_date(baldwin_birth, wedding)
    assert age == 52

    # Before birthday: April 1, 2018 -> 51
    age_before_bday = TemporalEngine.age_on_date(baldwin_birth, date(2018, 4, 1))
    assert age_before_bday == 51


# -----------------------------------------------------------------------------
# 5. Numerical Executor Tests
# -----------------------------------------------------------------------------

def test_numerical_executor_operators():
    """Verifies integer arithmetic, argmax, and set intersection."""
    # Addition: 40 + 9 = 49
    res_add = NumericalExecutor.execute("ADD", [40, 9])
    assert res_add.result == 49

    # Difference: 55 - 22 = 33
    res_sub = NumericalExecutor.execute("SUB", [55, 22])
    assert res_sub.result == 33

    # Argmax
    res_argmax = NumericalExecutor.execute("ARGMAX", [("Player A", 10), ("Player B", 25), ("Player C", 14)])
    assert res_argmax.result == "Player B"


# -----------------------------------------------------------------------------
# 6. Table Reasoning Tests: Second-Chance Fallback
# -----------------------------------------------------------------------------

def test_table_reasoning_second_chance_fallback():
    """Verifies semantic row/col matching when exact cell coordinate lookup is missing."""
    md_table = (
        "| Country | Population (M) | Capital |\n"
        "| --- | --- | --- |\n"
        "| France | 67.8 | Paris |\n"
        "| Germany | 83.2 | Berlin |\n"
        "| Italy | 59.0 | Rome |\n"
    )
    table = TableReasoningEngine.parse_markdown_table(md_table, title="Demographics")
    assert table is not None
    assert len(table.rows) == 3

    # Exact match
    val, method = TableReasoningEngine.find_cell_with_fallback(table, "France", "Capital")
    assert val == "Paris"
    assert method == "EXACT_COORDINATE"

    # Fuzzy row match
    val_fuzzy, method_fuzzy = TableReasoningEngine.find_cell_with_fallback(table, "Italian Republic", "Capital")
    assert val_fuzzy == "Rome" or "Rome" in val_fuzzy

    # Fallback to row when column name is inexact
    val_row, method_row = TableReasoningEngine.find_cell_with_fallback(table, "Germany", "Inhabitants")
    assert "83.2" in val_row
    assert method_row == "ROW_FALLBACK"


# -----------------------------------------------------------------------------
# 7. Grounding Verifier & Claim Graph: Derived Answers Without Literal Tokens
# -----------------------------------------------------------------------------

def test_grounding_verifier_derived_answer_bypass():
    """Fixes Q29/Princess Diana: Derived answer (Harold Wilson) accepted without verbatim token in text."""
    verifier = GroundingVerifier()
    
    context_chunks = [
        {"chunk_id": "c1", "text": "James Callaghan served as Prime Minister from 1976 to 1979."},
        {"chunk_id": "c2", "text": "Harold Wilson was Prime Minister from 1964 to 1970 and 1974 to 1976."},
    ]
    reasoning_trace = (
        "Princess Diana was born in 1961. Born three years earlier gives 1958. "
        "At that date, Harold Wilson was Prime Minister. Therefore, Harold Wilson."
    )
    
    is_grounded, proof_type, reason = verifier.verify_answer(
        candidate_answer="Harold Wilson",
        context_chunks=context_chunks,
        reasoning_trace=reasoning_trace,
    )
    assert is_grounded is True
    assert proof_type in (ProofType.DIRECT_PROOF, ProofType.DERIVED_PROOF)


# -----------------------------------------------------------------------------
# 8. Calibrated Abstention Gate Tests
# -----------------------------------------------------------------------------

def test_calibrated_abstention_gate_complete_proof():
    """Verifies that complete proof graphs never abstain even if model expressed doubt."""
    proof_graph = ProofGraph()
    proof_graph.register_hop(1, "Find Discoverer", "Zirconium", RelationType.DISCOVERED_BY)
    proof_graph.hops[1].status = "RESOLVED"
    
    chunks = [{"chunk_id": "c1", "text": "Martin Heinrich Klaproth discovered zirconium in 1789."}]
    
    should_abstain, decision, rationale = AbstentionGate.evaluate(
        proof_graph=proof_graph,
        context_chunks=chunks,
        candidate_answer="Martin Heinrich Klaproth",
    )
    assert should_abstain is False
    assert decision == AbstentionDecision.ANSWER


def test_calibrated_abstention_gate_empty_context():
    """Verifies clean abstention when zero context is available."""
    should_abstain, decision, _ = AbstentionGate.evaluate(
        proof_graph=None,
        context_chunks=[],
        candidate_answer="",
    )
    assert should_abstain is True
    assert decision == AbstentionDecision.ABSTAIN_EMPTY_CONTEXT


# -----------------------------------------------------------------------------
# 9. Surface-Form Constraint Adapter Tests (Q30)
# -----------------------------------------------------------------------------

def test_surface_constraint_adapter_words_and_rounding():
    """Fixes Q30: Converts 2000000 -> 'Two million.' when prompt requests words/characters."""
    prompt = "Write the answer to the nearest million, in characters."
    raw_answer = "2000000"
    adapted = SurfaceConstraintAdapter.adapt(raw_answer, prompt)
    assert adapted == "Two million."

    # Test with commas and decimals
    prompt2 = "What was the population rounded to nearest thousand, in words?"
    adapted2 = SurfaceConstraintAdapter.adapt("1,450,200", prompt2)
    assert "thousand" in adapted2.lower()


# -----------------------------------------------------------------------------
# 10. Program-Aided Reasoning (PoT) Letter & Char Counting (Q54)
# -----------------------------------------------------------------------------

def test_numerical_executor_letter_and_char_count():
    """Fixes Q54: The Young Americans alphanumeric letter count is 17 (vs LLM hallucinated 7)."""
    title = "The Young Americans"
    # "The" (3) + "Young" (5) + "Americans" (9) = 17 letters
    res = NumericalExecutor.execute("LETTER_COUNT", [title])
    assert res.result == 17
    assert res.operator == "LETTER_COUNT"

    # Char count with spaces included
    res_char = NumericalExecutor.execute("CHAR_COUNT", [title])
    assert res_char.result == len(title)


# -----------------------------------------------------------------------------
# 11. Table Engine Header Normalization with Footnotes & Currency
# -----------------------------------------------------------------------------

def test_table_engine_header_cleaning_footnotes_and_units():
    """Verifies table cell extraction when headers have footnote markers or currency symbols."""
    md_table = (
        "| Institution | Endowment ($M)[1] | State |\n"
        "| --- | --- | --- |\n"
        "| Stanford University | 36500 | California |\n"
        "| Harvard University | 50900 | Massachusetts |\n"
    )
    parsed = TableReasoningEngine.parse_markdown_table(md_table, title="University Endowments")
    assert parsed is not None

    # Query without footnote or dollar sign
    val, method = TableReasoningEngine.find_cell_with_fallback(parsed, "Harvard University", "Endowment")
    assert val == "50900"


# -----------------------------------------------------------------------------
# 12. Retrieval Scoping by Allowed Sources (Cross-Sample State Contamination Guard)
# -----------------------------------------------------------------------------

def test_isolated_harness_retrieval_allowed_sources_scoping():
    """Verifies that retrieval strictly respects allowed_sources filter to prevent batch cross-contamination."""
    if IsolatedFramesHarness is None:
        pytest.skip("IsolatedFramesHarness is not available")
    harness = IsolatedFramesHarness()
    passages = [
        {
            "chunk_id": "p_q15",
            "text": "Bratislava Film Festival is held annually in Bratislava.",
            "source_url": "https://en.wikipedia.org/wiki/Bratislava_Film_Festival",
            "title": "Bratislava Film Festival",
        },
        {
            "chunk_id": "p_q24",
            "text": "Giorgio Rognoni played midfielder. Demetrio Albertini was born in Besana in Brianza, Italy.",
            "source_url": "https://en.wikipedia.org/wiki/Demetrio_Albertini",
            "title": "Demetrio Albertini",
        },
    ]
    harness.ingest_evaluation_passages(passages)

    # Scoped to Q15 source only
    q15_sources = {"https://en.wikipedia.org/wiki/Bratislava_Film_Festival"}
    res = harness.retrieve_hybrid("born in what town", top_k=4, allowed_sources=q15_sources)
    
    # Must NOT retrieve Demetrio Albertini / Besana in Brianza
    retrieved_cids = [c["chunk_id"] for c in res["fused_chunks"]]
    assert "p_q24" not in retrieved_cids
    assert all("Besana in Brianza" not in c.get("text", "") for c in res["fused_chunks"])

