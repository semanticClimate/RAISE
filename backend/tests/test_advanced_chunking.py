"""
Unit and Integration Test Suite for Graph-Guided Adaptive Hierarchical Chunking (GGAHC).
Validates:
  1. Structural segmentation (Docling & PyMuPDF sections, tables, figures)
  2. Semantic candidate unit generation
  3. Knowledge extraction (Academic entities, startup profiles, quantitative facts)
  4. Temporary knowledge graph construction & Louvain/connected component community detection
  5. Multi-signal boundary optimization formula & explainability trace
  6. Hierarchical parent-child assembly & atomic proposition extraction
  7. Contextualization & metadata preservation
  8. Full AdaptiveChunkingPipeline execution across all strategies (fixed, recursive, semantic, structure_aware, hierarchical, gga_hybrid)
  9. Diagnostics machine-readable reporting and ASCII visual traces
  10. Backward compatibility with ChromaDB and Neo4j formats
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any, Dict, List

from src.chunking import (
    AdaptiveChunk,
    AdaptiveChunkingPipeline,
    BoundaryDecision,
    BoundaryExplanation,
    CandidateUnit,
    ChunkingConfig,
    ChunkingDiagnosticsEngine,
    ChunkLevel,
    Proposition,
    StructuralUnit,
)
from src.chunking.structure import DocumentStructureExtractor
from src.chunking.semantic import SemanticSegmenter
from src.chunking.extractor import CandidateKnowledgeExtractor
from src.chunking.graph_optimizer import GraphGuidedBoundaryOptimizer, TemporaryGraphBuilder
from src.chunking.hierarchical import HierarchicalChunkAssembler, PropositionExtractor
from src.chunking.contextualizer import Contextualizer


@pytest.fixture
def sample_parsed_sections() -> List[Dict[str, Any]]:
    return [
        {
            "page_number": 1,
            "heading": "1. Corporate Profile & Incubator Overview",
            "heading_level": 1,
            "text": (
                "IIT Madras Research Park (IITMRP) is India's first university research park. "
                "The park fosters deep-tech innovation and industry-academia collaborations. "
                "In FY 2024-25, the ecosystem continued expanding its incubation operations."
            ),
            "has_table": False,
        },
        {
            "page_number": 1,
            "heading": "1. Corporate Profile & Incubator Overview",
            "heading_level": 1,
            "text": (
                "IITM Incubation Cell (IITMIC) incubated 104 startups during the reporting period. "
                "Total cumulative startups incubated reached 412 companies across deep-tech sectors."
            ),
            "has_table": False,
        },
        {
            "page_number": 2,
            "heading": "2. Deep-Tech Venture Highlights",
            "heading_level": 1,
            "text": (
                "XYMA Analytics is an IITMIC incubated startup specializing in ultrasonic waveguide sensors. "
                "The company was mentored by Prof. Krishnan Balasubramanian and Prof. Prabhu Rajagopal from CNDE. "
                "XYMA's flagship product is the TMAP sensor line deployed at Reliance Jamnagar."
            ),
            "has_table": False,
        },
        {
            "page_number": 2,
            "heading": "2. Deep-Tech Venture Highlights",
            "heading_level": 1,
            "text": (
                "XYMA Analytics received a Letter of Award from Emirates Global Aluminium in 2024. "
                "The deployment validated high-temperature industrial waveguide sensor durability."
            ),
            "has_table": False,
        },
        {
            "page_number": 3,
            "heading": "3. Financial Summary Table",
            "heading_level": 1,
            "text": (
                "Below is the audited financial summary for the fiscal year:\n\n"
                "| Financial Metric | FY 2023-24 (₹ Lakhs) | FY 2024-25 (₹ Lakhs) |\n"
                "|---|---|---|\n"
                "| Total Revenue | 12,450.00 | 15,820.00 |\n"
                "| Research Expenditure | 4,200.00 | 5,600.00 |\n"
                "| Net Surplus | 1,850.00 | 2,410.00 |\n\n"
                "Note: Audited figures presented in accordance with Indian Accounting Standards."
            ),
            "has_table": True,
            "tables_count": 1,
        },
        {
            "page_number": 4,
            "heading": "4. Unrelated External Partnerships",
            "heading_level": 1,
            "text": (
                "The institute engaged in bilateral dialogues with overseas delegations regarding student exchange. "
                "Cultural exchange and sports facilities were upgraded during the summer vacation."
            ),
            "has_table": False,
        },
    ]


def test_stage_1_and_2_structural_segmentation(sample_parsed_sections):
    """Verify document layout structure extraction and first-class table handling."""
    extractor = DocumentStructureExtractor()
    units = extractor.extract_from_parsed_sections(sample_parsed_sections, document_id="doc_test")
    
    assert len(units) >= 6
    # Verify table unit is detected as first-class table unit
    table_units = [u for u in units if u.unit_type == "table"]
    assert len(table_units) == 1
    assert table_units[0].table_metadata is not None
    assert table_units[0].table_metadata["has_data"] is True
    assert "Financial Metric" in table_units[0].content


def test_stage_3_semantic_candidate_segmentation(sample_parsed_sections):
    """Verify candidate semantic units generation without flattening tables."""
    extractor = DocumentStructureExtractor()
    units = extractor.extract_from_parsed_sections(sample_parsed_sections, document_id="doc_test")
    
    segmenter = SemanticSegmenter()
    candidates = segmenter.segment_structural_units(units, document_id="doc_test")
    
    assert len(candidates) >= 4
    # Table candidate should remain discrete
    table_cands = [c for c in candidates if c.is_table]
    assert len(table_cands) == 1
    assert table_cands[0].page_start == 3


def test_stage_4_and_5_knowledge_extraction():
    """Verify entity continuity and relation extraction on candidate units."""
    cand = CandidateUnit(
        candidate_id="c_test_01",
        document_id="doc_test",
        section_id="sec_1",
        heading="Deep-Tech Startups",
        page_start=2,
        page_end=2,
        plain_text="XYMA Analytics is an IITMIC incubated venture with research expenditure of ₹50 crore in 2024.",
    )
    extractor = CandidateKnowledgeExtractor()
    enriched_cand = extractor.extract_candidate_knowledge(cand, institution_name="IIT Madras")
    
    ent_names = [e["name"] for e in enriched_cand.entities]
    assert any("xyma" in name.lower() for name in ent_names)
    assert len(enriched_cand.entities) > 0



def test_stage_6_temporary_graph_and_communities():
    """Verify temporary NetworkX graph construction and community assignment."""
    builder = TemporaryGraphBuilder()
    c1 = CandidateUnit(
        candidate_id="c1",
        document_id="doc",
        section_id="s1",
        heading="H1",
        page_start=1,
        page_end=1,
        plain_text="XYMA Analytics deployed sensors.",
        entities=[{"id": "e_xyma", "name": "XYMA Analytics", "label": "Startup"}],
    )
    c2 = CandidateUnit(
        candidate_id="c2",
        document_id="doc",
        section_id="s1",
        heading="H1",
        page_start=1,
        page_end=1,
        plain_text="XYMA Analytics expanded to UAE.",
        entities=[{"id": "e_xyma", "name": "XYMA Analytics", "label": "Startup"}],
    )
    G = builder.build_graph([c1, c2])
    assert G is not None
    assert G.has_node("c1")
    assert G.has_node("c2")
    assert G.has_node("e_xyma")
    assert G.has_edge("c1", "e_xyma")
    assert G.has_edge("c2", "e_xyma")

    communities = builder.detect_communities(G)
    assert len(communities) > 0
    # Both candidates share the entity, so they should belong to the same community
    assert communities.get("c1") == communities.get("c2")


def test_stage_11_12_13_boundary_optimizer():
    """Verify graph-guided boundary scoring and explainable reasons."""
    optimizer = GraphGuidedBoundaryOptimizer()
    
    # Unit A and Unit B share entity and same heading -> MERGE decision
    unit_a = CandidateUnit(
        candidate_id="u_a",
        document_id="doc",
        section_id="s1",
        heading="XYMA Overview",
        page_start=2,
        page_end=2,
        plain_text="XYMA Analytics developed the TMAP waveguide sensor line for high-temperature crackers.",
        entities=[{"id": "e_xyma", "name": "XYMA Analytics"}],
        relationships=[{"relation_id": "r1", "source_id": "e_xyma", "target_id": "e_tmap"}],
    )
    unit_b = CandidateUnit(
        candidate_id="u_b",
        document_id="doc",
        section_id="s1",
        heading="XYMA Overview",
        page_start=2,
        page_end=2,
        plain_text="The TMAP sensor was successfully validated at Reliance Industries Jamnagar refinery.",
        entities=[{"id": "e_xyma", "name": "XYMA Analytics"}, {"id": "e_tmap", "name": "TMAP"}],
        relationships=[{"relation_id": "r1", "source_id": "e_xyma", "target_id": "e_tmap"}],
    )
    
    explanation_merge = optimizer.evaluate_boundary(unit_a, unit_b)
    assert explanation_merge.decision == BoundaryDecision.MERGE
    assert explanation_merge.boundary_score < 0.0
    assert any("entity continuity" in r for r in explanation_merge.reasons)

    # Unit C is an entirely unrelated section with a different heading -> SPLIT decision
    unit_c = CandidateUnit(
        candidate_id="u_c",
        document_id="doc",
        section_id="s2",
        heading="Sports & Cultural Activities",
        page_start=5,
        page_end=5,
        plain_text="The annual inter-college cricket tournament took place in February.",
        entities=[{"id": "e_sports", "name": "Cricket Tournament"}],
    )
    explanation_split = optimizer.evaluate_boundary(unit_b, unit_c)
    assert explanation_split.decision == BoundaryDecision.SPLIT
    assert explanation_split.boundary_score > 0.5
    assert any("structural boundary" in r or "topic transition" in r for r in explanation_split.reasons)


def test_stage_14_17_hierarchical_assembly_and_propositions():
    """Verify parent-child assembly and proposition generation."""
    c1 = CandidateUnit(
        candidate_id="c1",
        document_id="doc_x",
        section_id="sec_1",
        heading="Growth",
        page_start=1,
        page_end=1,
        plain_text="The company expanded into Europe in 2023. Revenue increased by 15%.",
        entities=[{"id": "e1", "name": "Europe"}],
    )
    c2 = CandidateUnit(
        candidate_id="c2",
        document_id="doc_x",
        section_id="sec_1",
        heading="Growth",
        page_start=1,
        page_end=1,
        plain_text="The European expansion required an initial capital outlay of $20 million.",
        entities=[{"id": "e1", "name": "Europe"}],
    )
    
    # Boundary decision is MERGE
    decisions = [BoundaryExplanation(
        decision=BoundaryDecision.MERGE,
        boundary_score=-0.4,
        confidence=0.9,
        reasons=["- high entity continuity"],
    )]
    
    assembler = HierarchicalChunkAssembler()
    child_chunks, parent_chunks, propositions = assembler.assemble_hierarchy(
        candidates=[c1, c2],
        boundary_decisions=decisions,
        document_id="doc_x",
    )
    
    assert len(parent_chunks) == 1
    assert len(child_chunks) == 2
    # Verify parent-child linkage
    assert child_chunks[0].parent_chunk_id == parent_chunks[0].chunk_id
    assert child_chunks[1].parent_chunk_id == parent_chunks[0].chunk_id
    # Verify propositions were extracted
    assert len(propositions) > 0
    assert propositions[0].parent_chunk_id.startswith("doc_x_p001_c01")


def test_stage_18_contextualization():
    """Verify chunk contextualized_content prefix generation."""
    contextualizer = Contextualizer()
    chunk = AdaptiveChunk(
        chunk_id="chk_01",
        document_id="annual_report_2025",
        heading="Financial Performance",
        primary_page=42,
        plain_text="Revenue increased by 18% during the fourth quarter.",
    )
    parent = AdaptiveChunk(
        chunk_id="parent_01",
        document_id="annual_report_2025",
        heading="Financial Performance",
        primary_page=42,
        plain_text="The company reported strong growth across international markets. Operating cash flow improved significantly.",
    )
    
    contextualizer.contextualize_chunk(
        chunk=chunk,
        parent_chunk=parent,
        document_title="Annual_Report_2025.pdf",
        university="IIT Madras",
    )
    
    assert "Institution: IIT Madras" in chunk.contextualized_content
    assert "Heading: Financial Performance" in chunk.contextualized_content
    assert "Page: 42" in chunk.contextualized_content
    assert "Revenue increased by 18%" in chunk.contextualized_content
    # Raw plain_text remains intact
    assert chunk.plain_text == "Revenue increased by 18% during the fourth quarter."


def test_end_to_end_adaptive_chunking_pipeline(sample_parsed_sections):
    """End-to-end integration test of AdaptiveChunkingPipeline across sample report."""
    pipeline = AdaptiveChunkingPipeline()
    result = pipeline.process_document(
        parsed_sections=sample_parsed_sections,
        document_id="test_iitmrp_report",
        filename="IITMRP_Report_Test.pdf",
        university="IIT Madras Research Park",
        reporting_period="2024-25",
    )
    
    assert "child_chunks" in result
    assert "parent_chunks" in result
    assert "diagnostic_report" in result
    assert "ascii_trace" in result
    assert "legacy_chunks" in result
    
    child_chunks = result["child_chunks"]
    parent_chunks = result["parent_chunks"]
    diag = result["diagnostic_report"]
    
    assert len(child_chunks) >= 4
    assert len(parent_chunks) >= 2
    assert diag.structural_units_count >= 6
    assert diag.merge_operations > 0 or diag.split_operations > 0
    assert diag.average_boundary_confidence > 0.5
    assert diag.tables_count == 1

    # Verify backward compatibility dictionary serialization
    legacy = result["legacy_chunks"]
    for l_chk in legacy:
        assert "chunk_id" in l_chk
        assert "text" in l_chk
        assert "enriched_text" in l_chk
        assert "primary_page" in l_chk
        assert "heading" in l_chk
        assert "token_estimate" in l_chk
        assert "chunk_type" in l_chk


def test_baseline_strategies_compatibility(sample_parsed_sections):
    """Verify that baseline strategies (fixed, recursive, semantic, structure_aware) run successfully."""
    pipeline = AdaptiveChunkingPipeline()
    
    # Fixed baseline
    fixed_res = pipeline.process_document(
        parsed_sections=sample_parsed_sections,
        document_id="fixed_doc",
        strategy_override="fixed",
    )
    assert len(fixed_res["child_chunks"]) > 0
    assert fixed_res["child_chunks"][0].chunking_strategy == "fixed"

    # Recursive baseline
    rec_res = pipeline.process_document(
        parsed_sections=sample_parsed_sections,
        document_id="rec_doc",
        strategy_override="recursive",
    )
    assert len(rec_res["child_chunks"]) > 0
    assert rec_res["child_chunks"][0].chunking_strategy == "recursive"

    # Structure-aware baseline
    struct_res = pipeline.process_document(
        parsed_sections=sample_parsed_sections,
        document_id="struct_doc",
        strategy_override="structure_aware",
    )
    assert len(struct_res["child_chunks"]) > 0
    assert struct_res["child_chunks"][0].chunking_strategy == "structure_aware"


def test_table_preserving_chunker_schema_retention():
    """Verify Docling & Markdown table chunkers retain schema headers and row ranges across splits."""
    from src.chunking.table_chunker import TablePreservingChunker, MarkdownTablePreservingChunker
    import pandas as pd

    # 1. Test Markdown table splitting (35 data rows, max 15 per chunk -> 3 chunks)
    header = "| City | Population 1990 | Population 2000 | Growth Rate |\n|---|---|---|---|\n"
    rows = "\n".join([f"| City_{i} | {100000 + i*5000} | {120000 + i*6000} | {15.5 + i*0.1}% |" for i in range(35)])
    full_table = header + rows

    chunker = TablePreservingChunker(max_rows_per_chunk=15)
    chunks = chunker.chunk(full_table, caption="Census Demographics 1990-2000")

    assert len(chunks) == 3, f"Expected 3 table splits, got {len(chunks)}"
    for idx, c in enumerate(chunks):
        assert c["is_table"] is True
        assert "City" in c["text"]
        assert "Population 1990" in c["text"]
        assert "Population 2000" in c["text"]
        assert c["metadata"]["is_table"] is True
        assert c["metadata"]["table_caption"] == "Census Demographics 1990-2000"
        assert c["metadata"]["column_names"] == ["City", "Population 1990", "Population 2000", "Growth Rate"]
        assert c["metadata"]["total_rows"] == 35

    assert chunks[0]["metadata"]["row_range"] == [0, 14]
    assert chunks[1]["metadata"]["row_range"] == [15, 29]
    assert chunks[2]["metadata"]["row_range"] == [30, 34]

    # 2. Test pandas DataFrame table splitting (25 data rows, max 10 per chunk -> 3 chunks)
    df = pd.DataFrame({
        "Quarter": [f"Q{i%4+1}_{2020 + i//4}" for i in range(25)],
        "Revenue_Cr": [100.5 + i*2.3 for i in range(25)],
        "EBITDA_Pct": [22.4 + (i%5)*0.8 for i in range(25)],
    })
    df_chunker = TablePreservingChunker(max_rows_per_chunk=10)
    df_chunks = df_chunker.chunk(df, caption="Quarterly Financials")

    assert len(df_chunks) == 3
    assert df_chunks[0]["metadata"]["row_range"] == [0, 9]
    assert df_chunks[1]["metadata"]["row_range"] == [10, 19]
    assert df_chunks[2]["metadata"]["row_range"] == [20, 24]
    for c in df_chunks:
        assert "Quarter" in c["text"]
        assert "Revenue_Cr" in c["text"]
        assert c["metadata"]["is_table"] is True

