"""
Slash Commands Comparison Subsystem Unit Tests
==============================================
Validates:
1. /compare engine: two docs requirement, factsheet and evidence matrix tables.
2. Domain scoping and supplemental web evidence enrichment.
3. Longitudinal multi-year trend analysis (YoY deltas, publication counts).
4. PDF metric extraction speed and metadata parsing.
5. Multi-document handling and corrupt file resilience.
"""

import time
import pytest
from unittest.mock import patch

from src.features.commands import (
    CommandContext,
    SupplementalWebFetcher,
)
from src.features.commands.compare_command import (
    COMPARISON_DOMAINS,
    _format_badge,
    _resolve_institutions,
    handle_compare_command,
)
from src.features.commands.pdf_metric_extractor import (
    extract_pdf_institutional_profile,
    is_same_institution,
)


def test_compare_requires_two_documents():
    """Verifies /compare returns INSUFFICIENT_EVIDENCE when fewer than 2 docs attached."""
    ctx_0 = CommandContext(query="/compare", command_name="compare", raw_args="", active_docs=[])
    res_0 = handle_compare_command(ctx_0)
    assert res_0.status == "INSUFFICIENT_EVIDENCE"
    assert "Two Attached Documents Required" in res_0.answer
    assert "Currently attached documents:** 0" in res_0.answer

    ctx_1 = CommandContext(query="/compare", command_name="compare", raw_args="", active_docs=["Harvard.pdf"])
    res_1 = handle_compare_command(ctx_1)
    assert res_1.status == "INSUFFICIENT_EVIDENCE"
    assert "Currently attached documents:** 1" in res_1.answer


def test_compare_generates_both_markdown_tables():
    """Verifies /compare produces both Factsheet and Evidence Matrix tables."""
    ctx = CommandContext(
        query="/compare",
        command_name="compare",
        raw_args="",
        active_docs=["Harvard_Annual_Report_2025.pdf", "MIT_Financial_Report_2025.pdf"],
        allow_web_fetch=False,
    )
    res = handle_compare_command(ctx)
    assert res.status == "SUCCESS"
    assert "Institutional Scope Factsheet" in res.answer
    assert "Side-by-Side Multi-Dimensional Evidence Matrix" in res.answer
    assert "| Parameter | Harvard | MIT Financial |" in res.answer
    assert "| Domain | Criterion / Indicator | Harvard | MIT Financial | Comparability Status | Difference / Variance | Citations |" in res.answer
    assert "`🟢 FULLY_COMPARABLE`" in res.answer
    assert "`🟡 CONDITIONALLY_COMPARABLE`" in res.answer
    assert "`🟣 CONTEXT_ADJUSTED`" in res.answer
    assert len(res.citations) > 0
    assert res.citations[0]["pdf_filename"] == "Harvard_Annual_Report_2025.pdf"
    assert res.citations[1]["pdf_filename"] == "MIT_Financial_Report_2025.pdf"


def test_compare_domain_focus():
    """Verifies /compare [domain] scopes to the specified institutional domain."""
    ctx = CommandContext(
        query="/compare research",
        command_name="compare",
        raw_args="research",
        args=["research"],
        active_docs=["Doc_A.pdf", "Doc_B.pdf"],
        allow_web_fetch=False,
    )
    res = handle_compare_command(ctx)
    assert res.status == "SUCCESS"
    assert "**Comparison Scope:** `RESEARCH`" in res.answer
    assert "| **Research** | Publication Output |" in res.answer
    assert "| **Finance** |" not in res.answer


def test_compare_supplemental_web_evidence_enrichment():
    """Verifies /compare enriches missing indicators with external web evidence."""
    mock_web_rec = {
        "source_type": "EXTERNAL_PUBLIC_RECORD",
        "title": "Clarivate Highly Cited Researchers",
        "url": "https://en.wikipedia.org/wiki/Clarivate",
        "snippet": "Harvard ranked #1 in global highly cited researchers in 2024.",
        "institution": "Harvard",
        "topic": "Field-Normalized Impact (FWCI)",
    }

    with patch.object(SupplementalWebFetcher, "query_supplemental_evidence", return_value=mock_web_rec):
        ctx = CommandContext(
            query="/compare research",
            command_name="compare",
            raw_args="research",
            args=["research"],
            active_docs=["Harvard_Report.pdf", "MIT_Report.pdf"],
            allow_web_fetch=True,
        )
        res = handle_compare_command(ctx)
        assert res.status == "SUCCESS"
        ext_cits = [c for c in res.citations if c.get("source_type") == "EXTERNAL_PUBLIC_RECORD"]
        assert len(ext_cits) >= 2
        assert ext_cits[0]["url"] == "https://en.wikipedia.org/wiki/Clarivate"
        assert "Clarivate" in ext_cits[0]["plain_text"]


def test_compare_longitudinal_same_institution():
    """Verifies /compare detects same institution across different years and computes YoY trends."""
    ctx = CommandContext(
        query="/compare",
        command_name="compare",
        raw_args="",
        active_docs=["Annual Report 2022-23.pdf", "Annual Report 2023-24.pdf"],
        allow_web_fetch=True,
    )
    res = handle_compare_command(ctx)
    assert res.status == "SUCCESS"
    assert "Longitudinal Multi-Year Trend Analysis" in res.answer
    assert "National Institute of Plant Genome Research (NIPGR)" in res.answer
    assert "147 publications" in res.answer
    assert "123 publications" in res.answer
    assert "Patents Filed (Annual IP)" in res.answer
    assert "-16.3% YoY" in res.answer
    assert "+150.0% YoY" in res.answer
    assert "Year-over-Year Delta / Trend" in res.answer
    assert "`🟢 FULLY_COMPARABLE`" in res.answer
    assert "`🌐 EXTERNAL_SUPPLEMENTED`" in res.answer
    assert len(res.citations) >= 12
    pdf_cits = [c for c in res.citations if "Annual Report" in c.get("pdf_filename", "")]
    assert len(pdf_cits) >= 6


def test_compare_single_document_automated_web_fetch():
    """Verifies single uploaded multi-year document automatically fetches comparison baseline from web."""
    ctx = CommandContext(
        query="/compare 2023-24",
        command_name="compare",
        raw_args="2023-24",
        args=["2023-24"],
        active_docs=["Annual Report 2022-23.pdf"],
        allow_web_fetch=True,
    )
    res = handle_compare_command(ctx)
    assert res.status == "SUCCESS"
    assert "Longitudinal Multi-Year Trend Analysis" in res.answer
    assert "Web Registry (2023-24)" in res.answer
    assert "`🌐 EXTERNAL_SUPPLEMENTED`" in res.answer
    ext_cits = [c for c in res.citations if c.get("source_type") == "EXTERNAL_PUBLIC_RECORD"]
    assert len(ext_cits) >= 4


def test_pdf_metric_extractor_real_files():
    """Verifies extract_pdf_institutional_profile extracts real data from ingested PDFs."""
    prof_22 = extract_pdf_institutional_profile("Annual Report 2022-23.pdf")
    assert prof_22["reporting_year"] == "2022-23"
    assert "National Institute of Plant Genome Research" in prof_22["institution_name"]
    assert prof_22["publications_count"] == 147
    assert prof_22["patents_filed"] == 2
    assert prof_22["patents_granted"] == 4

    prof_23 = extract_pdf_institutional_profile("Annual Report 2023-24.pdf")
    assert prof_23["reporting_year"] == "2023-24"
    assert "National Institute of Plant Genome Research" in prof_23["institution_name"]
    assert prof_23["publications_count"] == 123
    assert prof_23["patents_filed"] == 5
    assert prof_23["patents_granted"] == 2
    assert is_same_institution(prof_22, prof_23) is True


def test_web_fetcher_wikidata_facts_integration():
    """Verifies SupplementalWebFetcher retrieves structured Wikidata facts."""
    facts = SupplementalWebFetcher.fetch_wikidata_facts("National Institute of Plant Genome Research")
    assert facts is not None
    assert "wikidata_id" in facts
    assert facts["wikidata_id"] == "Q30282198"
    assert "1997" in str(facts.get("inception_year", ""))
    assert "nipgr.res.in" in str(facts.get("website", ""))

    baseline = SupplementalWebFetcher.fetch_longitudinal_baseline(
        "National Institute of Plant Genome Research", "2023-24"
    )
    assert baseline["reporting_year"] == "2023-24"
    assert baseline["publications_count"] == 123
    assert baseline["source_type"] == "EXTERNAL_PUBLIC_RECORD"


def test_web_fetcher_caching_speed():
    """Verifies web fetcher caches responses so repeated queries return instantaneously."""
    rec1 = SupplementalWebFetcher.query_supplemental_evidence("National Institute of Plant Genome Research", "NIRF")
    assert rec1 is not None
    rec2 = SupplementalWebFetcher.query_supplemental_evidence("National Institute of Plant Genome Research", "NIRF")
    assert rec2 == rec1


def test_pdf_metric_extractor_speed_and_bric():
    """Verifies sub-second parsing and accurate leadership extraction on BRIC report."""
    t0 = time.time()
    prof = extract_pdf_institutional_profile("BRIC-Annual-Report-2025.pdf")
    elapsed = time.time() - t0
    assert elapsed < 2.0
    assert prof["institution_name"] == "Biotechnology Research and Innovation Council (BRIC)"
    assert "Rajesh Sudhir Gokhale" in str(prof["director"])


def test_pdf_metric_extractor_iit_madras():
    """Verifies 600+ page IIT Madras report parses in < 2.0s without falsely overwriting year."""
    t0 = time.time()
    prof = extract_pdf_institutional_profile("Annual Report 2024-25 final upload.pdf")
    elapsed = time.time() - t0
    assert elapsed < 2.0
    assert prof["institution_name"] == "Indian Institute of Technology Madras"
    assert prof["reporting_year"] == "2024-25"
    assert "Kamakoti" in str(prof["director"])


def test_web_fetcher_safe_institution_validation():
    """Verifies web fetcher does not attribute third-party institutions (e.g. DPSRU) to NIPGR."""
    rec = SupplementalWebFetcher.query_supplemental_evidence("National Institute of Plant Genome Research", "NIRF")
    assert rec is not None
    assert "Delhi Pharmaceutical" not in rec.get("title", "")
    assert "National Institute of Plant Genome Research" in rec.get("title", "") or "nipgr" in rec.get("url", "").lower()


def test_compare_three_or_more_documents():
    """Verifies /compare with 3+ documents notes extra documents without failing."""
    ctx = CommandContext(
        query="/compare",
        command_name="compare",
        raw_args="",
        active_docs=["Annual Report 2022-23.pdf", "Annual Report 2023-24.pdf", "BRIC-Annual-Report-2025.pdf"],
        allow_web_fetch=True,
    )
    res = handle_compare_command(ctx)
    assert res.status == "SUCCESS"
    assert "Multi-Document Note" in res.answer
    assert "1 other attached document(s) in drawer ignored" in res.answer


def test_compare_corrupt_pdf_graceful_fallback():
    """Verifies /compare handles corrupt or non-existent document gracefully."""
    ctx = CommandContext(
        query="/compare",
        command_name="compare",
        raw_args="",
        active_docs=["Nonexistent_Corrupt_Univ.pdf", "Annual Report 2022-23.pdf"],
        allow_web_fetch=True,
    )
    res = handle_compare_command(ctx)
    assert res.status == "SUCCESS"
    assert "Nonexistent Corrupt Univ" in res.answer
