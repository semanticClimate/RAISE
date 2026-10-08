"""
Adaptive Chunking Pipeline Master Coordinator (Stage 44, 47 of GGAHC).
======================================================================
Component: `src.chunking.pipeline`
Architecture Layer: Document Processing / Master Chunking Pipeline

Integrates all stages:
  1. Document Intelligence & Structural Segmentation
  2. Candidate Semantic Segmentation
  3. Entity & Relationship Extraction
  4. Temporary Knowledge Graph Construction & Community Detection
  5. Multi-Signal Graph-Guided Boundary Optimization
  6. Hierarchical Unit Assembly & Proposition Extraction
  7. Contextualization & Bounded Late Chunking
  8. Diagnostics, Statistics & Explainable Boundary Reporting

Modular Architecture:
---------------------
- Baseline Chunking Strategies: `src.chunking.baselines`
- Boundary Evaluation Runner & Rust FFI: `src.chunking.boundary_runner`
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .config import ChunkingConfig
from .contextualizer import BoundedLateChunker, Contextualizer
from .diagnostics import ChunkingDiagnosticsEngine
from .extractor import CandidateKnowledgeExtractor
from .graph_optimizer import GraphGuidedBoundaryOptimizer, TemporaryGraphBuilder
from .hierarchical import HierarchicalChunkAssembler
from .models import (
    CandidateUnit,
    EvidenceBundle,
    StructuralUnit,
)
from .semantic import SemanticSegmenter
from .structure import DocumentStructureExtractor

# Modular re-exports for 100% backward compatibility
from .baselines import (
    process_fixed_baseline,
    process_recursive_baseline,
)
from .boundary_runner import (
    evaluate_candidate_boundaries,
)

logger = logging.getLogger("raise.chunking.pipeline")


class AdaptiveChunkingPipeline:
    """
    Master coordinator for Graph-Guided Adaptive Hierarchical Chunking (GGAHC).
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.structure_extractor = DocumentStructureExtractor()
        self.semantic_segmenter = SemanticSegmenter(self.config)
        self.knowledge_extractor = CandidateKnowledgeExtractor()
        self.graph_builder = TemporaryGraphBuilder()
        self.boundary_optimizer = GraphGuidedBoundaryOptimizer(self.config)
        self.hierarchical_assembler = HierarchicalChunkAssembler(self.config)
        self.contextualizer = Contextualizer(self.config)
        self.late_chunker = BoundedLateChunker(self.config)
        self.diagnostics_engine = ChunkingDiagnosticsEngine()

    def process_document(
        self,
        parsed_sections: List[Dict[str, Any]],
        document_id: str,
        filename: str = "",
        university: str = "Institution",
        reporting_period: str = "2024-25",
        total_pages: Optional[int] = None,
        strategy_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end adaptive chunking across the specified or configured strategy.
        Returns:
          {
            "child_chunks": List[AdaptiveChunk],
            "parent_chunks": List[AdaptiveChunk],
            "propositions": List[Proposition],
            "diagnostic_report": ChunkingDiagnosticReport,
            "ascii_trace": str,
            "legacy_chunks": List[Dict[str, Any]],
          }
        """
        strat = strategy_override or self.config.strategy
        pages = total_pages or (max([s.get("page_number", 1) for s in parsed_sections]) if parsed_sections else 1)
        failures: List[str] = []

        # -------------------------------------------------------------
        # Dispatch baseline strategies if requested
        # -------------------------------------------------------------
        if strat == "fixed":
            return self._process_fixed_baseline(parsed_sections, document_id, filename, university, reporting_period, pages)
        elif strat == "recursive":
            return self._process_recursive_baseline(parsed_sections, document_id, filename, university, reporting_period, pages)

        # -------------------------------------------------------------
        # STAGE 1 & 2: Structural Segmentation
        # -------------------------------------------------------------
        try:
            structural_units = self.structure_extractor.extract_from_parsed_sections(
                sections=parsed_sections,
                document_id=document_id,
            )
        except Exception as e:
            failures.append(f"Structure extraction fallback: {e}")
            structural_units = [
                StructuralUnit(
                    unit_id=f"{document_id}_u{i}",
                    unit_type="paragraph",
                    content=s.get("text", ""),
                    heading=s.get("heading", f"Section {i}"),
                    heading_level=3,
                    page_number=s.get("page_number", 1),
                )
                for i, s in enumerate(parsed_sections, start=1)
            ]

        # -------------------------------------------------------------
        # STAGE 3: Semantic Segmentation (Candidate Units)
        # -------------------------------------------------------------
        try:
            candidates = self.semantic_segmenter.segment_structural_units(
                structural_units=structural_units,
                document_id=document_id,
            )
        except Exception as e:
            failures.append(f"Semantic segmentation fallback: {e}")
            candidates = [
                CandidateUnit(
                    candidate_id=f"{document_id}_cand_{i}",
                    document_id=document_id,
                    section_id=f"sec_{document_id}_{u.page_number}",
                    heading=u.heading,
                    page_start=u.page_number,
                    page_end=u.page_number,
                    plain_text=u.content,
                    structural_unit_ids=[u.unit_id],
                    is_table=(u.unit_type == "table"),
                    is_figure=(u.unit_type == "figure"),
                )
                for i, u in enumerate(structural_units, start=1)
            ]

        # -------------------------------------------------------------
        # STAGE 4 & 5: Entity and Relation Extraction for Candidates
        # -------------------------------------------------------------
        try:
            candidates = self.knowledge_extractor.extract_batch(
                candidates=candidates,
                institution_name=university,
            )
        except Exception as e:
            failures.append(f"Entity/relation extraction fallback: {e}")

        # -------------------------------------------------------------
        # STAGE 6: Temporary Knowledge Graph & Community Detection
        # -------------------------------------------------------------
        temp_graph = None
        node_to_comm: Dict[str, str] = {}
        if strat == "gga_hybrid" and not self.config.ablation_disable_community_continuity:
            try:
                temp_graph = self.graph_builder.build_graph(candidates)
                if temp_graph:
                    node_to_comm = self.graph_builder.detect_communities(temp_graph)
                    for c in candidates:
                        c.community_id = node_to_comm.get(c.candidate_id)
            except Exception as e:
                failures.append(f"Temporary graph construction fallback: {e}")

        # -------------------------------------------------------------
        # STAGE 11, 12, 13: Graph-Guided Boundary Optimization
        # -------------------------------------------------------------
        boundary_decisions = evaluate_candidate_boundaries(
            candidates=candidates,
            config=self.config,
            strat=strat,
            temp_graph=temp_graph,
            node_to_comm=node_to_comm,
            boundary_optimizer=self.boundary_optimizer,
        )

        # -------------------------------------------------------------
        # STAGE 14 - 17: Hierarchical Assembly & Propositions
        # -------------------------------------------------------------
        child_chunks, parent_chunks, propositions = self.hierarchical_assembler.assemble_hierarchy(
            candidates=candidates,
            boundary_decisions=boundary_decisions,
            document_id=document_id,
            university=university,
            strategy=strat,
            filename=filename,
        )

        # -------------------------------------------------------------
        # STAGE 18: Contextualization
        # -------------------------------------------------------------
        self.contextualizer.contextualize_batch(
            child_chunks=child_chunks,
            parent_chunks=parent_chunks,
            document_title=filename,
            university=university,
            reporting_period=reporting_period,
        )

        # -------------------------------------------------------------
        # STAGE 42 & 43: Diagnostics & ASCII Trace
        # -------------------------------------------------------------
        diag_report = self.diagnostics_engine.build_report(
            document_id=document_id,
            filename=filename,
            strategy=strat,
            pages=pages,
            structural_units=structural_units,
            candidates=candidates,
            child_chunks=child_chunks,
            parent_chunks=parent_chunks,
            propositions=propositions,
            boundary_decisions=boundary_decisions,
            failures=failures,
        )

        ascii_trace = self.diagnostics_engine.render_ascii_trace(
            candidates=candidates,
            boundary_decisions=boundary_decisions,
        )

        # Assemble Evidence Bundles
        evidence_bundles: List[EvidenceBundle] = []
        if self.config.enable_evidence_bundles:
            for c in child_chunks:
                ent_ids = [e["id"] for e in c.entities if "id" in e]
                table_str = c.plain_text if c.is_table else None
                b_text = c.plain_text if not c.is_table else ""
                bundle = EvidenceBundle(
                    bundle_id=f"bundle_{c.chunk_id}",
                    primary_chunk_id=c.chunk_id,
                    document_id=document_id,
                    heading_hierarchy=[c.heading],
                    text_content=b_text,
                    table_content=table_str,
                    referenced_entity_ids=ent_ids,
                    source_page=c.primary_page,
                    is_complete=True,
                )
                evidence_bundles.append(bundle)

        legacy_chunks = [c.to_dict() for c in child_chunks]

        return {
            "child_chunks": child_chunks,
            "parent_chunks": parent_chunks,
            "propositions": propositions,
            "evidence_bundles": evidence_bundles,
            "diagnostic_report": diag_report,
            "ascii_trace": ascii_trace,
            "legacy_chunks": legacy_chunks,
        }

    def _process_fixed_baseline(
        self,
        parsed_sections: List[Dict[str, Any]],
        document_id: str,
        filename: str,
        university: str,
        reporting_period: str,
        pages: int,
    ) -> Dict[str, Any]:
        """Fixed-size chunking baseline helper."""
        return process_fixed_baseline(
            parsed_sections=parsed_sections,
            document_id=document_id,
            filename=filename,
            university=university,
            reporting_period=reporting_period,
            pages=pages,
        )

    def _process_recursive_baseline(
        self,
        parsed_sections: List[Dict[str, Any]],
        document_id: str,
        filename: str,
        university: str,
        reporting_period: str,
        pages: int,
    ) -> Dict[str, Any]:
        """Recursive character chunking baseline helper."""
        return process_recursive_baseline(
            parsed_sections=parsed_sections,
            document_id=document_id,
            filename=filename,
            university=university,
            reporting_period=reporting_period,
            pages=pages,
        )
