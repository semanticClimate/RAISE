"""
RAISE Graph Construction & Entity Extraction Subsystem
=======================================================
Purpose:
  Populates NetworkX property graphs from academic entity-relationship triples
  and parses unstructured section chunks into typed knowledge nodes and edges.

Entity Classification & Visual Palette:
  - University / Institute: #2563eb (Deep Blue, Size 24)
  - Department / Division: #0284c7 (Sky Blue, Size 24)
  - Centre / Facility: #0d9488 (Teal, Size 24)
  - Programs & Subjects: #7c3aed / #9333ea (Purple, Size 16)
  - Faculty & Leadership: #16a34a / #059669 (Emerald / Mint, Size 18)
  - Grants & Financials: #ca8a04 (Amber, Size 18)
  - Publications & Patents: #e11d48 (Rose, Size 16)

Author: RAISE Core Architecture Team
Maintainability: Keep under 250 lines with defensive normalization routines.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
import networkx as nx


def slugify(text: str) -> str:
    """Sanitizes strings for safe node identifiers and Cypher variable names."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(text).strip())


def build_from_academic_triples(
    graph: nx.DiGraph,
    node_provenance: Dict[str, Dict[str, Any]],
    triples_data: List[Dict[str, Any]],
    doc_id: str = "default",
) -> Dict[str, Any]:
    """
    Populate NetworkX graph from extracted academic entity and relation triples.
    """
    color_map = {
        "University": "#2563eb",
        "Department": "#0284c7",
        "Centre": "#0d9488",
        "Program": "#7c3aed",
        "Subject": "#9333ea",
        "Practical_Lab": "#c026d3",
        "AcademicRegulation": "#ea580c",
        "EligibilityRequirement": "#d97706",
        "Faculty_Person": "#16a34a",
        "AdministrativeRole": "#059669",
        "ResearchProject": "#4f46e5",
        "Publication_Patent": "#e11d48",
        "MetricFact": "#ca8a04",
    }

    for item in triples_data:
        for ent in item.get("entities", []):
            nid = ent["entity_id"]
            label = ent.get("name", nid)
            ntype = ent.get("label", "Entity")
            props = ent.get("properties", {})
            prov = ent.get("provenance", {})

            graph.add_node(
                nid,
                id=nid,
                label=label,
                type=ntype,
                properties=props,
                provenance=prov,
                color=color_map.get(ntype, "#64748b"),
                size=24 if ntype in ["University", "Department", "Centre"] else 16,
                page=prov.get("page_number", 1),
            )
            node_provenance[nid] = prov

        for rel in item.get("relations", []):
            src = rel["source_id"]
            tgt = rel["target_id"]
            rtype = rel.get("relation_type", "RELATED_TO")
            props = rel.get("properties", {})
            prov = rel.get("provenance", {})

            if graph.has_node(src) and graph.has_node(tgt):
                graph.add_edge(
                    src,
                    tgt,
                    relation=rtype,
                    type=rtype,
                    properties=props,
                    provenance=prov,
                )

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }


def build_from_chunks(
    graph: nx.DiGraph,
    chunks: List[Dict[str, Any]],
    taxonomy_report: Optional[Dict[str, Any]] = None,
    doc_id: str = "default",
) -> Dict[str, Any]:
    """
    Perform deep multi-entity extraction and construct directed relationship graph.
    """
    # 1. Root Document Node
    graph.add_node(
        doc_id,
        type="Document",
        label=f"Document: {doc_id}",
        color="#2563eb",
        size=28,
        page=1,
    )

    known_orgs: Dict[str, str] = {}
    known_persons: Dict[str, str] = {}
    known_grants: Dict[str, str] = {}

    for idx, chunk in enumerate(chunks):
        cid = str(chunk.get("chunk_id") or f"{doc_id}_chunk_{idx}")
        heading = str(chunk.get("heading") or f"Section {idx+1}")
        page = int(chunk.get("source_pages", [1])[0] if chunk.get("source_pages") else 1)
        task = str(chunk.get("recommended_task") or "general")
        text = str(chunk.get("plain_text") or "")
        if not text.strip():
            continue

        # Add Section Node
        graph.add_node(
            cid,
            type="Section",
            label=heading[:38] + ("..." if len(heading) > 38 else ""),
            heading=heading,
            page=page,
            task=task,
            color="#0ea5e9",
            size=18,
        )
        graph.add_edge(doc_id, cid, relation="CONTAINS_SECTION")

        # Entity Extraction: Standard and regex discovered organizations
        current_section_orgs = []
        standard_orgs = [
            "BRIC", "CDFD", "NIPGR", "DBT", "AstraBio Innovations Council", "Indian Institute of Technology Madras",
            "IIT Madras Research Park", "Panjab University", "Delhi University", "JNU", "CSIR", "ICMR", "DST", "AIIMS"
        ]
        discovered_orgs = set(standard_orgs)
        found_insts = re.findall(r"\b([A-Z][A-Za-z\s&]{3,40}(?:Institute|Council|University|Foundation|Centre|Center|Laboratory|Board))\b", text)
        for inst in found_insts:
            clean_inst = inst.strip()
            if 4 < len(clean_inst) < 45 and not clean_inst.startswith("The "):
                discovered_orgs.add(clean_inst)

        for org_name in discovered_orgs:
            if org_name.lower() in text.lower():
                org_id = f"org_{slugify(org_name)}"
                if org_id not in known_orgs:
                    known_orgs[org_id] = org_name
                    graph.add_node(
                        org_id,
                        type="Organization",
                        label=org_name,
                        color="#10b981",
                        size=24,
                        page=page,
                    )
                graph.add_edge(cid, org_id, relation="MENTIONS_ORGANIZATION")
                current_section_orgs.append(org_id)

        # Leaders/Persons
        person_matches = re.finditer(r"(?:Dr\.|Prof\.|Mr\.|Ms\.|Director|Dean)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", text)
        for pm in person_matches:
            p_name = pm.group(0).strip()
            p_id = f"person_{slugify(p_name)}"
            if p_id not in known_persons:
                known_persons[p_id] = p_name
                graph.add_node(
                    p_id,
                    type="Person",
                    label=p_name,
                    color="#f59e0b",
                    size=18,
                    page=page,
                )
            graph.add_edge(cid, p_id, relation="MENTIONS_LEADERSHIP")
            for o_id in current_section_orgs:
                graph.add_edge(p_id, o_id, relation="LEADS_OR_GOVERNS")

        # Funding Grants
        grant_matches = re.finditer(r"(?:₹|Rs\.?|INR|\$)\s*([0-9]+(?:\.[0-9]+)?\s*(?:Crore|Crores|Lakh|Lakhs|Million|Billion))", text, re.IGNORECASE)
        for gm in grant_matches:
            g_val = gm.group(0).strip()
            g_id = f"grant_{slugify(g_val)}"
            if g_id not in known_grants:
                known_grants[g_id] = g_val
                graph.add_node(
                    g_id,
                    type="FundingAllocation",
                    label=f"Metric: {g_val}",
                    color="#ca8a04",
                    size=18,
                    page=page,
                )
            graph.add_edge(cid, g_id, relation="REPORTS_FINANCIALS")

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
