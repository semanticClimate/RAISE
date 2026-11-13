"""
Academic Personnel, Organizations, and Metric Fact Extractor
============================================================
Component: `src.features.ingestion.academic_personnel_facts`
Architecture: Helper extraction submodule for faculty, committees, and metrics
Line Ceiling: Strictly <= 400 lines
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .academic_models import AcademicEntity, AcademicRelation


def extract_personnel_and_metrics(
    text: str,
    section_heading: str,
    pdf_filename: str,
    page_number: int,
    chunk_id: str,
    uni_id: str,
    add_entity: Callable[[str, str, str, Optional[Dict[str, Any]]], None],
    relations: List[AcademicRelation],
) -> None:
    """Extracts faculty, leadership roles, committees, organizations, and metric facts."""

    # 1. Detect active department in this section/chunk
    active_dept_id = None
    active_dept_name = None
    dept_m = re.search(r"\b((?:Department|School|Division)\s+of\s+[A-Za-z\s&]{3,40})\b", section_heading + " " + text[:300], re.IGNORECASE)
    if dept_m:
        active_dept_name = dept_m.group(1).strip()
        active_dept_id = f"dept_{re.sub(r'[^a-zA-Z0-9]', '_', active_dept_name.lower())[:40]}"
        add_entity(active_dept_id, "Department", active_dept_name, None)

    # 2. Detect active committee/board in this section/chunk
    active_comm_id = None
    active_comm_name = None
    comm_m = re.search(r"\b([A-Z][a-zA-Z0-9\s&]{2,40}\s+(?:Board|Committee|Council|Governors))\b", section_heading + " " + text[:300])
    if comm_m:
        active_comm_name = comm_m.group(1).strip()
        active_comm_id = f"org_{re.sub(r'[^a-zA-Z0-9]', '_', active_comm_name.lower())[:35]}"
        add_entity(active_comm_id, "Organization", active_comm_name, None)

    # 3. Faculty names with titles
    fac_pattern = re.compile(r"\b(Prof\.|Dr\.|Shri|Ms\.|Mr\.|Col\s*\(Retd\))\s+([A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){1,4})", re.IGNORECASE)
    for fm in fac_pattern.finditer(text):
        fac_title = fm.group(1).strip()
        fac_raw_name = fm.group(2).strip()
        fac_name = f"{fac_title} {fac_raw_name}"
        if any(w.lower() in fac_raw_name.lower() for w in ["annual report", "table", "section", "academic", "university", "department", "degree"]):
            continue
        f_id = f"fac_{re.sub(r'[^a-zA-Z0-9]', '_', fac_name.lower())[:30]}"
        add_entity(f_id, "Faculty_Person", fac_name, {"title": fac_title})

        if active_dept_id and active_dept_name:
            relations.append(AcademicRelation(
                relation_id=f"rel_{f_id}_{active_dept_id}_member_of",
                source_id=f_id,
                source_label="Faculty_Person",
                relation_type="MEMBER_OF_DEPARTMENT",
                target_id=active_dept_id,
                target_label="Department",
                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
            ))

        snippet_after = text[fm.end():fm.end()+150]
        role_m = re.search(r"^\s*,\s*([A-Za-z0-9\s&,()–\-]{3,60}?)(?:[;\n\.]|\s*Ex\s+officio|\s*Member\b|\s*Chairman\b|\s*Secretary\b|\s*$)", snippet_after)
        if role_m:
            role_str = role_m.group(1).strip()
            if len(role_str) > 2 and any(k in role_str.lower() for k in ["dean", "director", "chair", "member", "secretary", "registrar", "head", "advisor", "warden", "officer", "professor", "president", "vice-chancellor", "ceo", "cfo"]):
                role_id = f"role_{re.sub(r'[^a-zA-Z0-9]', '_', role_str.lower())[:35]}"
                add_entity(role_id, "AdministrativeRole", role_str, None)
                relations.append(AcademicRelation(
                    relation_id=f"rel_{f_id}_{role_id}_holds_role",
                    source_id=f_id,
                    source_label="Faculty_Person",
                    relation_type="HOLDS_ROLE",
                    target_id=role_id,
                    target_label="AdministrativeRole",
                    provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                ))

        if active_comm_id and active_comm_name:
            if any(k in snippet_after.lower() for k in ["chairman", "chairperson", "presiding"]):
                rel_type = "CHAIRS"
            elif any(k in snippet_after.lower() for k in ["secretary", "member - secretary", "member – secretary"]):
                rel_type = "SECRETARY_OF"
            else:
                rel_type = "MEMBER_OF_COMMITTEE"
            relations.append(AcademicRelation(
                relation_id=f"rel_{f_id}_{active_comm_id}_{rel_type.lower()}",
                source_id=f_id,
                source_label="Faculty_Person",
                relation_type=rel_type,
                target_id=active_comm_id,
                target_label="Organization",
                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
            ))

    # 4. Organizations, Boards, Committees, and Regulatory Bodies
    org_matches = re.finditer(r"\b([A-Z][a-zA-Z0-9\s&]{2,35}\s+(?:Limited|Ltd\.?|Corporation|Exchange|Board|Committee|Council|Bank|Securities|Fund|Authority|Association|Trust))\b", text)
    for om in org_matches:
        org_name = om.group(1).strip()
        o_id = f"org_{re.sub(r'[^a-zA-Z0-9]', '_', org_name.lower())[:35]}"
        add_entity(o_id, "Organization", org_name, None)
        relations.append(AcademicRelation(
            relation_id=f"rel_{uni_id}_{o_id}_partner",
            source_id=uni_id,
            source_label="University",
            relation_type="PARTNERED_WITH",
            target_id=o_id,
            target_label="Organization",
            provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
        ))
        relations.append(AcademicRelation(
            relation_id=f"rel_{chunk_id}_{o_id}_mentions",
            source_id=chunk_id,
            source_label="Chunk",
            relation_type="MENTIONS",
            target_id=o_id,
            target_label="Organization",
            provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
        ))

    # 5. Financial & Metric Facts
    metric_matches = re.finditer(
        r"((?:₹|rs\.?|inr|\$|usd|€|eur)\s*[\d,]+(?:\.\d+)?\s*(?:crores?|lakhs?|cr|lac|millions?|billions?|bn|mn|k)?|"
        r"[\d,]+(?:\.\d+)?\s*(?:crores?|lakhs?|cr|lac|millions?|billions?|bn|mn)\s*(?:inr|usd|rupees)?|"
        r"[\d,]+(?:\.\d+)?\s*%|"
        r"[\d,]+(?:\.\d+)?\s*(?:ipos|listed entities|registered investors|startups|patents|students|faculty|trades|messages))",
        text, re.IGNORECASE
    )
    for idx, mm in enumerate(metric_matches):
        raw_val = mm.group(1).strip()
        fact_phrase = text[max(0, mm.start()-40):min(len(text), mm.end()+40)].strip()
        fact_id = f"fact_{chunk_id}_{idx+1}"
        add_entity(fact_id, "MetricFact", f"Metric: {raw_val}", {"raw_value": raw_val, "context": fact_phrase})
        relations.append(AcademicRelation(
            relation_id=f"rel_{uni_id}_{fact_id}_reported_metric",
            source_id=uni_id,
            source_label="University",
            relation_type="REPORTED_METRIC",
            target_id=fact_id,
            target_label="MetricFact",
            provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
        ))
        relations.append(AcademicRelation(
            relation_id=f"rel_{chunk_id}_{fact_id}_has_fact",
            source_id=chunk_id,
            source_label="Chunk",
            relation_type="HAS_FACT",
            target_id=fact_id,
            target_label="MetricFact",
            provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
        ))

    # 6. Section & Chunk Nodes
    sec_id = f"sec_{re.sub(r'[^a-zA-Z0-9]', '_', section_heading.lower())[:35]}"
    add_entity(sec_id, "Section", section_heading, {"page": page_number, "pdf": pdf_filename})
    relations.append(AcademicRelation(
        relation_id=f"rel_{uni_id}_{sec_id}_has_section",
        source_id=uni_id,
        source_label="University",
        relation_type="HAS_SECTION",
        target_id=sec_id,
        target_label="Section",
        provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
    ))

    add_entity(chunk_id, "Chunk", f"Passage (p.{page_number})", {"text_preview": text[:150], "page": page_number, "pdf": pdf_filename})
    relations.append(AcademicRelation(
        relation_id=f"rel_{sec_id}_{chunk_id}_contains",
        source_id=sec_id,
        source_label="Section",
        relation_type="CONTAINS_CHUNK",
        target_id=chunk_id,
        target_label="Chunk",
        provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
    ))


__all__ = ["extract_personnel_and_metrics"]
