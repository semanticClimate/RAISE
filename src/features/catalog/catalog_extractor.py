"""
RAISE OKF Catalog Extractor & Ingestion Profiler
================================================
Based on the Google Cloud Open Knowledge Format (OKF) specification:
https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/

Automatically generates Open Knowledge Format (OKF) document profiles (.okf.md)
for any PDF ingested at runtime, while chunks and entities are being created.

How OKF Increases AI Response Accuracy:
----------------------------------------
1. Zero-Hardcoding Dynamic Routing:
   Resolves user query constraints against the registered OKF metadata (institution aliases,
   acronyms, fiscal years) without requiring any hardcoded document lookup tables in code.
2. Temporal Disambiguation:
   Enforces exact reporting periods (e.g., 2022-23 vs 2023-24 vs 2025) and standalone year
   negative lookarounds, preventing cross-annual retrieval mixing and hallucinated year comparisons.
3. Acronym & Entity Expansion:
   Disambiguates domain-specific acronyms (e.g., E3a -> Early Flowering 3a, NIPGR -> National
   Institute of Plant Genome Research), allowing dense and BM25 retrievers to retrieve relevant
   chunks even when query terminology differs from the document text.
4. Grounded Citation Provenance:
   Maps every chunk to verified cataloged document metadata, ensuring that LLM generation cites
   genuine document and page provenance without inventing references.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.features.catalog.knowledge_catalog import (
    DocumentKnowledgeProfile,
    KnowledgeCatalogRegistry,
)

logger = logging.getLogger("raise.features.catalog.extractor")


def extract_okf_profile_from_pdf(
    pdf_path: Path,
    chunks: Optional[List[Dict[str, Any]]] = None,
    entities: Optional[List[Any]] = None,
    facts: Optional[List[Dict[str, Any]]] = None,
    institution_name: Optional[str] = None,
    reporting_period: Optional[str] = None,
    registry: Optional[KnowledgeCatalogRegistry] = None,
) -> DocumentKnowledgeProfile:
    """
    Analyzes an uploaded PDF document and generates an agent-ready OKF profile (.okf.md).
    Extracts institution identity, temporal periods, domain taxonomy, key entities,
    section outlines, and financial/statistical summaries while chunks are created.
    """
    if registry is None:
        registry = KnowledgeCatalogRegistry.get_instance()

    pdf_filename = pdf_path.name
    doc_stem = pdf_path.stem

    # 1. Read first few pages text if available
    header_text = ""
    total_pages = 0
    try:
        import pymupdf
        doc = pymupdf.open(str(pdf_path))
        total_pages = len(doc)
        sample_pages = min(10, total_pages)
        for i in range(sample_pages):
            header_text += doc[i].get_text("text") + "\n"
        doc.close()
    except Exception as e:
        logger.warning("PyMuPDF extraction notice for %s: %s", pdf_filename, e)
        if chunks:
            header_text = "\n".join([(c.get("plain_text") or c.get("text") or "") for c in chunks[:12]])
            total_pages = max([c.get("primary_page", 1) for c in chunks] or [1])

    # 2. Extract Reporting Period & Fiscal Years
    extracted_period = reporting_period or ""
    fiscal_years: Set[str] = set()

    if not extracted_period:
        fy_match = re.search(r"\b(20\d{2}[-–/]\d{2})\b", header_text)
        if fy_match:
            extracted_period = fy_match.group(1).replace("–", "-").replace("/", "-")
        else:
            single_yr = re.search(r"\b(20\d{2})\b", header_text)
            if single_yr:
                extracted_period = single_yr.group(1)

    # Also check filename for years
    fn_fy = re.search(r"\b(20\d{2}[-–/]\d{2})\b", doc_stem)
    if fn_fy:
        rp = fn_fy.group(1).replace("–", "-").replace("/", "-")
        if not extracted_period:
            extracted_period = rp
        fiscal_years.update([rp, rp[:4], "20" + rp[-2:]])
    elif re.search(r"\b(20\d{2})\b", doc_stem):
        sy = re.search(r"\b(20\d{2})\b", doc_stem).group(1)
        if not extracted_period:
            extracted_period = sy
        fiscal_years.add(sy)

    if extracted_period:
        fiscal_years.add(extracted_period)
        if "-" in extracted_period and len(extracted_period) == 7:
            start_yr = extracted_period[:4]
            end_yr = "20" + extracted_period[-2:]
            fiscal_years.update([start_yr, end_yr])

    # 3. Extract Institution Name & Aliases
    final_institution = institution_name or ""
    short_name = ""
    aliases: List[str] = []

    if not final_institution:
        inst_match = re.search(
            r"(National\s+Institute\s+of\s+[A-Za-z\s]+|Biotechnology\s+Research\s+and\s+Innovation\s+Council|"
            r"National\s+Brain\s+Research\s+Centre|Translational\s+Health\s+Science\s+and\s+Technology\s+Institute|"
            r"[A-Z][a-zA-Z\s]+University|[A-Z][a-zA-Z\s]+Institute\s+of\s+Technology)",
            header_text,
        )
        if inst_match:
            final_institution = inst_match.group(1).strip()
        else:
            final_institution = doc_stem.replace("_", " ").replace("-", " ")

    # Short name / Acronym extraction
    acronym_match = re.search(r"\b([A-Z]{2,8})\b", final_institution)
    if acronym_match:
        short_name = acronym_match.group(1)
    else:
        # Dynamically discover primary uppercase acronym from header or document title
        cands = re.findall(r"\b([A-Z]{2,8})\b", f"{doc_stem} {header_text[:2500]}")
        filtered_cands = [c for c in cands if c not in {"PDF", "DOC", "THE", "FOR", "AND", "PAGE", "VOL", "YEAR", "HTTP", "WWW"}]
        short_name = filtered_cands[0] if filtered_cands else None

    if short_name and short_name not in aliases:
        aliases.append(short_name)
    if final_institution and final_institution not in aliases:
        aliases.append(final_institution)

    # 4. Extract Key Entities from Entities argument and text chunks
    key_entities: Set[str] = set()
    key_acronyms: Dict[str, str] = {}
    section_map: Dict[str, int] = {}
    table_map: Dict[str, int] = {}

    if entities:
        for ent in entities:
            e_name = getattr(ent, "name", "") if hasattr(ent, "name") else ent.get("name", "")
            if e_name and len(e_name) > 3 and not e_name.startswith("Chunk "):
                key_entities.add(e_name)

    text_to_mine = header_text
    if chunks:
        for c in chunks:
            c_text = c.get("plain_text") or c.get("text") or ""
            p_no = c.get("primary_page") or c.get("page") or 1
            sec_heading = c.get("heading") or c.get("section") or ""
            if sec_heading and len(sec_heading) > 4 and sec_heading not in section_map:
                section_map[sec_heading] = int(p_no)

            if c.get("is_table") or "|" in c_text:
                tbl_title = sec_heading or f"Table (Page {p_no})"
                if tbl_title not in table_map:
                    table_map[tbl_title] = int(p_no)

        text_to_mine += "\n" + "\n".join([(c.get("plain_text") or c.get("text") or "")[:400] for c in chunks[:50]])

    # Gene / Protein / Academic markers (e.g. OsMADS26, At-SLX1, CaMYB39, miR164e)
    gene_matches = re.findall(r"\b([A-Z][a-z]{1,2}[A-Z0-9_\-]{2,12})\b", text_to_mine)
    for g in gene_matches:
        if len(g) >= 4 and not g.startswith("HTTP") and not g.startswith("ISBN") and not g.isdigit():
            key_entities.add(g)

    # PIs and Researchers
    pi_matches = re.findall(r"(?:PI|Principal Investigator|Director|Head|Lead)[:\s]+([A-Z][a-zA-Z\s\.]+)", text_to_mine)
    for pi in pi_matches:
        pi_clean = pi.split("\n")[0].split(";")[0].split(",")[0].strip()
        if 4 < len(pi_clean) < 40 and not any(w in pi_clean.lower() for w in ["annual", "report", "table", "section"]):
            key_entities.add(pi_clean)

    # Acronym definitions (e.g. "Early Flowering 3a (E3a)")
    pair_matches = re.findall(r"([A-Z][a-zA-Z0-9\s\-]{3,35})\s*\(([A-Z0-9]{2,8})\)", text_to_mine)
    for exp, acr in pair_matches:
        if len(acr) >= 2 and acr.isupper() and acr not in ("THE", "AND", "FOR", "NOT"):
            key_acronyms[acr] = exp.strip()
            key_entities.add(exp.strip())

    sorted_entities = sorted(list(key_entities))[:35]

    # 5. Extract Domains
    domains = ["Life Sciences", "Biotechnology"]
    t_lower = text_to_mine.lower()
    if any(k in t_lower for k in ["plant", "genome", "crop", "chickpea", "rice", "arabidopsis"]):
        domains.append("Plant Genomics & Agriculture")
    if any(k in t_lower for k in ["brain", "neuro", "cognitive", "synapse"]):
        domains.append("Neuroscience & Cognitive Science")
    if any(k in t_lower for k in ["vaccine", "dengue", "infectious", "pathogen", "clinical"]):
        domains.append("Translational Health & Immunology")
    if any(k in t_lower for k in ["bio-manufacturing", "bioeconomy", "fermentation", "enzymes"]):
        domains.append("Bio-Manufacturing & Industrial Biotechnology")

    # 6. Extract Statistical Footprint
    stat_lines: List[str] = []
    if facts:
        for f in facts[:8]:
            m_name = getattr(f, "metric_name", "") or getattr(f, "name", "") or (f.get("metric_name", "") if isinstance(f, dict) else "")
            raw_v = getattr(f, "raw_value", "") or (getattr(f, "properties", {}).get("raw_value") if hasattr(f, "properties") else "") or (f.get("raw_value", "") if isinstance(f, dict) else "")
            if m_name and raw_v:
                stat_lines.append(f"- **{str(m_name).replace('_', ' ').title()}:** {raw_v}")

    # Section index lines
    section_lines = [f"- `{heading}` (Page {page})" for heading, page in list(section_map.items())[:10]]
    table_lines = [f"- `{title}` (Page {page})" for title, page in list(table_map.items())[:8]]

    # 7. Build OKF Markdown Content with complete documentation
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", doc_stem)
    body_md = f"""# {final_institution} ({extracted_period})

## 1. Institutional Identity & Context
The **{final_institution}** ({short_name or 'N/A'}) is an autonomous scientific institution reported under document `{pdf_filename}`.
This Open Knowledge Format (OKF) profile provides agent-ready metadata for zero-hardcoding dynamic routing, temporal disambiguation, and verified citation provenance.

## 2. Research Domains & Academic Scope
- **Primary Domains:** {', '.join(domains)}
- **Total Monitored Pages:** {total_pages}
- **Document Scope:** {extracted_period} (Fiscal Years: {', '.join(sorted(list(fiscal_years)))})

## 3. Key Entities & Scientific Assets
{chr(10).join([f"- `{e}`" for e in sorted_entities[:20]])}

## 4. Key Acronyms & Expanded Nomenclature
{chr(10).join([f"- **{acr}:** {exp}" for acr, exp in list(key_acronyms.items())[:12]])}

## 5. Major Report Sections & Page Index
{chr(10).join(section_lines) if section_lines else "- General Technical & Research Report"}

## 6. Financial & Tabular Schedules
{chr(10).join(table_lines) if table_lines else "- Schedules and tabular data indexed in context chunks"}

## 7. Operational & Quantitative Indicators
{chr(10).join(stat_lines) if stat_lines else f"- Total Pages: {total_pages}"}
"""

    profile = DocumentKnowledgeProfile(
        document_id=safe_id,
        filename=pdf_filename,
        institution_name=final_institution,
        short_name=short_name,
        aliases=aliases,
        reporting_period=extracted_period,
        fiscal_years=sorted(list(fiscal_years)),
        document_type="annual_report",
        total_pages=total_pages,
        primary_domains=domains,
        key_entities=sorted_entities,
        key_acronyms=key_acronyms,
        overview_text=body_md.strip(),
    )

    registry.register_profile(profile, persist=True)
    logger.info("Persisted dynamic OKF profile for %s (%s)", pdf_filename, extracted_period)
    return profile


def auto_ensure_okf_catalogs(
    upload_dir: Optional[Path] = None,
    processed_dir: Optional[Path] = None,
    registry: Optional[KnowledgeCatalogRegistry] = None,
) -> int:
    """
    Automated pipeline self-healing:
    Scans the uploaded PDFs directory and processed chunks directory.
    If any document is missing its corresponding .okf.md file, the pipeline
    automatically extracts and persists the OKF profile on the fly.
    Returns the number of freshly generated OKF profiles.
    """
    if registry is None:
        registry = KnowledgeCatalogRegistry.get_instance()

    catalog_dir = registry.catalog_dir
    catalog_dir.mkdir(parents=True, exist_ok=True)

    from src.core.config import DOCUMENTS_DIR, PROCESSED_DIR, CHUNKS_DIR
    candidate_doc_dirs = [
        upload_dir if upload_dir else None,
        DOCUMENTS_DIR,
    ]
    proc_dir = processed_dir or PROCESSED_DIR
    chunks_dir = proc_dir / "chunks" if hasattr(proc_dir, "__truediv__") else Path(proc_dir) / "chunks"

    generated_count = 0

    all_pdf_files: List[Path] = []
    for d in candidate_doc_dirs:
        if d and d.exists():
            all_pdf_files.extend(list(d.glob("*.pdf")))

    import json
    for pdf_file in all_pdf_files:
        safe_stem = pdf_file.stem.replace(" ", "_").replace("-", "_")
        okf_file = catalog_dir / f"{safe_stem}.okf.md"

        if not okf_file.exists():
            matches = list(catalog_dir.glob(f"*{safe_stem}*.okf.md"))
            if not matches:
                chunks = None
                chunk_candidates = [
                    chunks_dir / f"{pdf_file.name}_chunks.json",
                    chunks_dir / f"{pdf_file.stem}_chunks.json",
                    chunks_dir / f"{safe_stem}_chunks.json",
                ]
                for cc in chunk_candidates:
                    if cc.exists():
                        try:
                            chunks = json.loads(cc.read_text(encoding="utf-8"))
                            break
                        except Exception:
                            pass

                try:
                    logger.info("Pipeline auto-generating missing OKF profile for: %s", pdf_file.name)
                    extract_okf_profile_from_pdf(pdf_path=pdf_file, chunks=chunks, registry=registry)
                    generated_count += 1
                except Exception as ex:
                    logger.warning("Pipeline auto OKF generation failed for %s: %s", pdf_file.name, ex)

    registry.reload_catalogs()
    return generated_count

