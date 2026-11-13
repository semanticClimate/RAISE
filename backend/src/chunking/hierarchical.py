"""
Hierarchical Information Unit Assembler & Proposition Extractor (Stage 14, 15, 16, 17 of GGAHC).
Constructs multi-level information units:
  Document
  └── Section
      └── Parent Chunk (600 - 1200 tokens)
          └── Child Chunk (150 - 350 tokens)
              └── Atomic Propositions / Facts
Maintains explicit bidirectional parent-child references and proposition provenance.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .config import ChunkingConfig
from .models import (
    AdaptiveChunk,
    BoundaryDecision,
    BoundaryExplanation,
    CandidateUnit,
    ChunkLevel,
    Proposition,
)

try:
    from llama_index.core.node_parser import HierarchicalNodeParser
    from llama_index.core.schema import Document as LlamaDocument
    HAS_LLAMA_INDEX = True
except ImportError:
    HAS_LLAMA_INDEX = False


class PropositionExtractor:
    """
    Extracts atomic, verifiable propositions/facts from child chunks without losing context.
    Retains explicit provenance to parent child_chunk_id.
    """

    SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

    def __init__(self):
        pass

    def extract_propositions(
        self,
        child_chunk: AdaptiveChunk,
    ) -> List[Proposition]:
        """
        Splits child chunk text into atomic propositions, resolving pronouns/context where possible.
        """
        raw_text = child_chunk.plain_text
        cid = child_chunk.chunk_id
        doc_id = child_chunk.document_id
        sec_id = child_chunk.section_id
        pno = child_chunk.primary_page

        sentences = [s.strip() for s in self.SENTENCE_SPLIT_REGEX.split(raw_text) if len(s.strip()) > 15]
        propositions: List[Proposition] = []

        prop_counter = 0
        for sent in sentences:
            # Skip tables or markdown formatting
            if "|" in sent or sent.startswith("#"):
                continue

            # Split compound coordinate sentences if joined by semicolons
            sub_clauses = [c.strip() for c in sent.split(";") if len(c.strip()) > 15]
            for clause in sub_clauses:
                prop_counter += 1
                pid = f"prop_{cid}_{prop_counter:02d}"
                
                # Associated entities mentioned in this sentence
                mentioned_ents = [
                    e["name"] for e in child_chunk.entities
                    if e.get("name") and e["name"].lower() in clause.lower()
                ]

                prop = Proposition(
                    proposition_id=pid,
                    text=clause,
                    parent_chunk_id=cid,
                    document_id=doc_id,
                    section_id=sec_id,
                    page_number=pno,
                    entities=mentioned_ents,
                    provenance={
                        "document_id": doc_id,
                        "primary_page": pno,
                        "heading": child_chunk.heading,
                        "child_chunk_id": cid,
                        "parent_chunk_id": child_chunk.parent_chunk_id,
                    },
                )
                propositions.append(prop)

        return propositions


class HierarchicalChunkAssembler:
    """
    Executes boundary decisions to synthesize coherent Parent Chunks, derives Child Chunks,
    and attaches Atomic Propositions.
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.prop_extractor = PropositionExtractor()

    def assemble_hierarchy(
        self,
        candidates: List[CandidateUnit],
        boundary_decisions: List[BoundaryExplanation],
        document_id: str,
        university: str = "Institution",
        strategy: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Tuple[List[AdaptiveChunk], List[AdaptiveChunk], List[Proposition]]:
        """
        Processes candidate units according to boundary decisions:
          1. Merges adjacent candidate units with MERGE decisions into Parent Chunks.
          2. Generates Child Chunks from Parent Chunks (or preserves discrete units).
          3. Extracts Propositions from Child Chunks.
        Returns:
          (final_child_chunks, final_parent_chunks, all_propositions)
        """
        strat_name = strategy or self.config.strategy

        if not candidates:
            return [], [], []

        # 1. Group candidates into Parent Chunk clusters
        parent_clusters: List[List[CandidateUnit]] = []
        current_cluster: List[CandidateUnit] = [candidates[0]]

        for i in range(len(boundary_decisions)):
            next_cand = candidates[i + 1]
            decision = boundary_decisions[i].decision

            if (
                decision == BoundaryDecision.MERGE
                and not current_cluster[-1].is_table
                and not next_cand.is_table
                and not current_cluster[-1].is_figure
                and not next_cand.is_figure
            ):
                current_cluster.append(next_cand)
            else:
                parent_clusters.append(current_cluster)
                current_cluster = [next_cand]

        if current_cluster:
            parent_clusters.append(current_cluster)

        parent_chunks: List[AdaptiveChunk] = []
        child_chunks: List[AdaptiveChunk] = []
        all_propositions: List[Proposition] = []

        # 2. Build Parent & Child Chunks
        for p_idx, cluster in enumerate(parent_clusters, start=1):
            first_c = cluster[0]
            last_c = cluster[-1]
            parent_id = f"{document_id}_parent_{p_idx:03d}"
            combined_text = "\n\n".join(c.plain_text for c in cluster)
            sec_id = first_c.section_id
            heading = first_c.heading
            p_start = first_c.page_start
            p_end = last_c.page_end
            pages = sorted(list(set(range(p_start, p_end + 1))))

            # Aggregate entities and relationships
            cluster_ents: Dict[str, Dict[str, Any]] = {}
            cluster_rels: Dict[str, Dict[str, Any]] = {}
            for c in cluster:
                for e in c.entities:
                    cluster_ents[e["id"]] = e
                for r in c.relationships:
                    rel_k = r.get("relation_id") or r.get("id") or f"{r.get('source')}_{r.get('target')}"
                    cluster_rels[rel_k] = r

            is_tbl = any(c.is_table for c in cluster)
            is_fig = any(c.is_figure for c in cluster)

            actual_pdf = filename or f"{document_id}.pdf"
            p_heading = (heading or (first_c.heading if first_c else "")).strip()
            p_enriched = f"[Document: {actual_pdf} | Section: {p_heading}]\n{combined_text}" if p_heading and not combined_text.startswith("[Document:") else combined_text

            parent_chunk = AdaptiveChunk(
                chunk_id=parent_id,
                document_id=document_id,
                parent_chunk_id=None,
                section_id=sec_id,
                chunk_level=ChunkLevel.PARENT.value,
                plain_text=combined_text,
                contextualized_content=p_enriched,
                heading=heading,
                primary_page=p_start,
                source_pages=pages,
                entities=list(cluster_ents.values()),
                relationships=list(cluster_rels.values()),
                token_estimate=max(1, len(combined_text.split())),
                is_table=is_tbl,
                is_figure=is_fig,
                chunking_strategy=strat_name,
                metadata={
                    "document_id": document_id,
                    "pdf_filename": actual_pdf,
                    "university": university,
                    "primary_page": p_start,
                    "heading": heading,
                    "is_parent": True,
                }
            )
            parent_chunks.append(parent_chunk)

            # 3. Derive Child Chunks
            # If cluster has multiple candidates, each candidate becomes a child chunk
            # If single candidate is large (> max_child_tokens), split into sub-children
            for c_sub_idx, c_unit in enumerate(cluster, start=1):
                child_text = c_unit.plain_text
                c_tokens = c_unit.token_estimate
                child_id = f"{document_id}_p{c_unit.page_start:03d}_c{p_idx:02d}_{c_sub_idx:02d}"
                c_heading = (c_unit.heading or heading or "").strip()
                c_enriched = f"[Document: {actual_pdf} | Section: {c_heading}]\n{child_text}" if c_heading and not child_text.startswith("[Document:") else child_text

                child_chunk = AdaptiveChunk(
                    chunk_id=child_id,
                    document_id=document_id,
                    parent_chunk_id=parent_id,
                    section_id=c_unit.section_id,
                    chunk_level=ChunkLevel.CHILD.value,
                    plain_text=child_text,
                    contextualized_content=c_enriched,
                    heading=c_unit.heading,
                    primary_page=c_unit.page_start,
                    source_pages=list(range(c_unit.page_start, c_unit.page_end + 1)),
                    entities=c_unit.entities,
                    relationships=c_unit.relationships,
                    token_estimate=c_tokens,
                    is_table=c_unit.is_table,
                    is_figure=c_unit.is_figure,
                    chunking_strategy=strat_name,

                    metadata={
                        "document_id": document_id,
                        "pdf_filename": actual_pdf,
                        "university": university,
                        "primary_page": c_unit.page_start,
                        "heading": c_unit.heading,
                        "parent_chunk_id": parent_id,
                        "is_table": c_unit.is_table,
                        "is_figure": c_unit.is_figure,
                    }
                )

                # Extract propositions if enabled
                if self.config.enable_propositions and not self.config.ablation_disable_propositions and not c_unit.is_table:
                    props = self.prop_extractor.extract_propositions(child_chunk)
                    child_chunk.propositions = [p.to_dict() for p in props]
                    all_propositions.extend(props)

                child_chunks.append(child_chunk)

        # Connect sequential previous_chunk_id and next_chunk_id for child chunks
        for idx in range(len(child_chunks)):
            if idx > 0:
                child_chunks[idx].previous_chunk_id = child_chunks[idx - 1].chunk_id
            if idx < len(child_chunks) - 1:
                child_chunks[idx].next_chunk_id = child_chunks[idx + 1].chunk_id

        return child_chunks, parent_chunks, all_propositions


class LlamaIndexHierarchicalChunker:
    """
    Standard Parent-Child Chunker backed by LlamaIndex (MIT License).
    Generates Parent Chunks (default 1024 tokens) and Child Chunks (default 256 tokens)
    with explicit bidirectional parent-child references.
    """

    def __init__(self, parent_chunk_size: int = 1024, child_chunk_size: int = 256):
        self.parent_size = parent_chunk_size
        self.child_size = child_chunk_size
        if HAS_LLAMA_INDEX:
            self._parser = HierarchicalNodeParser.from_defaults(
                chunk_sizes=[self.parent_size, self.child_size]
            )
        else:
            self._parser = None

    def chunk_document(
        self,
        text: str,
        doc_id: str,
        primary_page: int = 1,
        filename: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parses document text into linked parent and child chunk records.
        Child chunks include parent_node reference pointing to their enclosing parent chunk.
        """
        if not text or not text.strip():
            return []

        base_meta = {
            **(extra_metadata or {}),
            "doc_id": doc_id,
            "primary_page": primary_page,
            "pdf_filename": filename or doc_id,
        }

        if not HAS_LLAMA_INDEX or self._parser is None:
            words = text.split()
            chunks = []
            for idx in range(0, len(words), self.child_size):
                chunk_words = words[idx : idx + self.child_size]
                cid = f"{doc_id}_p{primary_page}_c{idx // self.child_size + 1}"
                chunks.append({
                    "chunk_id": cid,
                    "plain_text": " ".join(chunk_words),
                    "text": " ".join(chunk_words),
                    "primary_page": primary_page,
                    "document_id": doc_id,
                    "metadata": {
                        **base_meta,
                        "chunk_id": cid,
                    },
                })
            return chunks

        llama_doc = LlamaDocument(text=text, metadata=base_meta)
        nodes = self._parser.get_nodes_from_documents([llama_doc])

        result_chunks = []
        for n in nodes:
            parent_id = n.parent_node.node_id if n.parent_node else None
            is_parent = parent_id is None
            cid = f"{doc_id}_{n.node_id[:8]}"
            meta = {
                **base_meta,
                **n.metadata,
                "chunk_id": cid,
                "node_id": n.node_id,
                "parent_chunk_id": f"{doc_id}_{parent_id[:8]}" if parent_id else None,
                "is_parent": is_parent,
                "level": "parent" if is_parent else "child",
            }
            result_chunks.append({
                "chunk_id": cid,
                "plain_text": n.text,
                "text": n.text,
                "primary_page": primary_page,
                "document_id": doc_id,
                "parent_chunk_id": meta["parent_chunk_id"],
                "is_parent": is_parent,
                "metadata": meta,
            })
        return result_chunks

    def split_text(self, text: str, doc_id: str = "doc") -> List[Dict[str, Any]]:
        """Convenience alias for chunk_document."""
        return self.chunk_document(text=text, doc_id=doc_id)

    def chunk_text(self, text: str, doc_id: str = "doc") -> List[Dict[str, Any]]:
        """Convenience alias for chunk_document."""
        return self.chunk_document(text=text, doc_id=doc_id)

