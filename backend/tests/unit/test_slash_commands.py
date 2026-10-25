"""
Comprehensive Unit Tests: Slash Commands & Web Fetcher Subsystem
================================================================
Validates:
1. Command registry, aliases, metadata, and dev-only filtering (isolation of /bench and /help).
2. Public exposure of /compare and /browser commands.
3. /audit engine: anti-hallucination verification and citation generation.
4. /synthesize engine: institutional synthesis and citations.
5. /graph engine: entity neighborhood traversal and subgraph payload.
6. /bench and /help dev commands.
7. /browser engine: direct URL extraction, search queries, and citation contract compliance.
8. SupplementalWebFetcher: HTML cleaning, protocol safety, and entity unescaping.
9. Chat bridge: slash command detection, global dispatching, and error wrapping.
"""

import html
import pytest
from unittest.mock import patch

from src.features.commands import (
    CommandContext,
    CommandRegistry,
    CommandResult,
    SupplementalWebFetcher,
    execute_slash_command,
    get_command_registry,
    is_slash_command,
)
from src.features.commands.compare_command import handle_compare_command
from src.features.commands.core_commands import (
    handle_audit_command,
    handle_bench_command,
    handle_browser_command,
    handle_graph_command,
    handle_help_command,
    handle_synthesize_command,
)


@pytest.fixture
def clean_registry():
    """Provides a fresh isolated CommandRegistry instance for testing."""
    reg = CommandRegistry()
    reg.register(
        name="compare",
        description="Side-by-side institutional comparison.",
        syntax="/compare [focus]",
        examples=["/compare research"],
        aliases=["diff", "versus", "vs"],
        category="Comparison",
    )(handle_compare_command)

    reg.register(
        name="audit",
        description="Strict anti-hallucination factual audit.",
        syntax="/audit [claim]",
        examples=["/audit patent counts"],
        aliases=["verify", "factcheck"],
        category="Verification",
        is_dev_only=True,
    )(handle_audit_command)

    reg.register(
        name="synthesize",
        description="Executive institutional synthesis.",
        syntax="/synthesize [focus]",
        examples=["/synthesize"],
        aliases=["summary"],
        category="Synthesis",
        is_dev_only=True,
    )(handle_synthesize_command)

    reg.register(
        name="graph",
        description="Knowledge graph entity traversal.",
        syntax="/graph [entity]",
        examples=["/graph Early Flowering 3a"],
        aliases=["explore", "kg"],
        category="Knowledge Graph",
        is_dev_only=True,
    )(handle_graph_command)

    reg.register(
        name="browser",
        description="Extract supplemental research facts from the internet.",
        syntax="/browser [url or query]",
        examples=["/browser NIRF IIT Madras"],
        aliases=["web", "fetch"],
        category="Research",
        is_dev_only=False,
    )(handle_browser_command)

    reg.register(
        name="bench",
        description="Benchmark evaluation diagnostics.",
        syntax="/bench",
        examples=["/bench"],
        aliases=["eval"],
        category="Diagnostics",
        is_dev_only=True,
    )(handle_bench_command)

    reg.register(
        name="help",
        description="Interactive reference card.",
        syntax="/help",
        examples=["/help"],
        aliases=["commands"],
        category="Help",
        is_dev_only=True,
    )(handle_help_command)

    return reg


# ==============================================================================
# 1. Registry & Dev Command Isolation Tests
# ==============================================================================

def test_registry_dev_command_filtering(clean_registry):
    """Verifies dev/diagnostic commands are hidden by default from UI list, exposing /compare and /browser."""
    user_cmds = clean_registry.list_commands(include_dev=False)
    user_names = [c.name for c in user_cmds]

    assert set(user_names) == {"/compare", "/browser"}
    assert "/audit" not in user_names
    assert "/synthesize" not in user_names
    assert "/graph" not in user_names
    assert "/bench" not in user_names
    assert "/help" not in user_names

    all_cmds = clean_registry.list_commands(include_dev=True)
    all_names = [c.name for c in all_cmds]
    assert "/bench" in all_names
    assert "/help" in all_names
    assert len(all_names) == 7


def test_registry_aliases_resolution(clean_registry):
    """Verifies registered aliases dispatch to the correct primary handlers."""
    assert clean_registry.get_handler("diff") == handle_compare_command
    assert clean_registry.get_handler("vs") == handle_compare_command
    assert clean_registry.get_handler("verify") == handle_audit_command
    assert clean_registry.get_handler("summary") == handle_synthesize_command
    assert clean_registry.get_handler("kg") == handle_graph_command
    assert clean_registry.get_handler("web") == handle_browser_command
    assert clean_registry.get_handler("eval") == handle_bench_command


def test_command_line_parsing(clean_registry):
    """Verifies shlex argument parsing and edge cases."""
    cmd, raw, args = clean_registry.parse_command_line("/compare research --depth=2")
    assert cmd == "compare"
    assert raw == "research --depth=2"
    assert args == ["research", "--depth=2"]

    cmd, raw, args = clean_registry.parse_command_line("/audit \"exact claim to check\"")
    assert cmd == "audit"
    assert args == ["exact claim to check"]

    cmd, raw, args = clean_registry.parse_command_line("regular conversational prompt")
    assert cmd is None
    assert args == []


# ==============================================================================
# 2. Core Commands Tests (/audit, /synthesize, /graph, /bench, /help)
# ==============================================================================

def test_audit_command_verification():
    """Verifies /audit checks numerical claims and generates document citations."""
    ctx = CommandContext(
        query="/audit patent count and budget",
        command_name="audit",
        raw_args="patent count and budget",
        active_docs=["Audit_2025.pdf"],
    )
    res = handle_audit_command(ctx)
    assert res.command == "/audit"
    assert res.status == "SUCCESS"
    assert "Audited Factual & Numerical Verification" in res.answer
    assert len(res.citations) > 0
    assert res.citations[0]["pdf_filename"] == "Audit_2025.pdf"


def test_synthesize_command_generation():
    """Verifies /synthesize synthesizes cross-document executive brief."""
    ctx = CommandContext(
        query="/synthesize strategic focus",
        command_name="synthesize",
        raw_args="strategic focus",
        active_docs=["Doc1.pdf", "Doc2.pdf"],
    )
    res = handle_synthesize_command(ctx)
    assert res.command == "/synthesize"
    assert res.status == "SUCCESS"
    assert "Audited Institutional Synthesis" in res.answer


def test_graph_command_subgraph_payload():
    """Verifies /graph returns structured node/edge subgraph payload."""
    ctx = CommandContext(
        query="/graph Early Flowering 3a",
        command_name="graph",
        raw_args="Early Flowering 3a",
    )
    res = handle_graph_command(ctx)
    assert res.command == "/graph"
    assert "nodes" in res.subgraph
    assert "edges" in res.subgraph
    assert len(res.subgraph["nodes"]) >= 3
    assert any(n["name"] == "Early Flowering 3a" for n in res.subgraph["nodes"])


def test_bench_and_help_commands():
    """Verifies /bench and /help dev commands produce expected reference output."""
    ctx_b = CommandContext(query="/bench", command_name="bench", raw_args="")
    res_b = handle_bench_command(ctx_b)
    assert res_b.command == "/bench"
    assert "BEIR (SciFact)" in res_b.answer
    assert "HotpotQA" in res_b.answer

    ctx_h = CommandContext(query="/help", command_name="help", raw_args="")
    res_h = handle_help_command(ctx_h)
    assert res_h.command == "/help"
    assert "/compare" in res_h.answer
    assert "/audit" in res_h.answer


# ==============================================================================
# 3. /browser Command & SupplementalWebFetcher Tests
# ==============================================================================

def test_browser_empty_query():
    """Verifies /browser without arguments prompts for query or URL."""
    ctx = CommandContext(query="/browser", command_name="browser", raw_args="")
    res = handle_browser_command(ctx)
    assert res.command == "/browser"
    assert "Please provide a search topic or web URL" in res.answer


def test_browser_direct_url_fetch():
    """Verifies /browser with direct URL extracts clean text with citation."""
    with patch.object(SupplementalWebFetcher, "fetch_url_text", return_value="Harvard endowment reached $53 billion in 2024."):
        ctx = CommandContext(
            query="/browser https://en.wikipedia.org/wiki/Harvard_Endowment",
            command_name="browser",
            raw_args="https://en.wikipedia.org/wiki/Harvard_Endowment",
        )
        res = handle_browser_command(ctx)
        assert res.command == "/browser"
        assert res.quality_gate_decision == "accept"
        assert "Audited External Web Extraction" in res.answer
        assert len(res.citations) == 1
        assert res.citations[0]["url"] == "https://en.wikipedia.org/wiki/Harvard_Endowment"


def test_browser_search_topic():
    """Verifies /browser with search query searches and formats evidence."""
    mock_rec = {
        "source_type": "EXTERNAL_PUBLIC_RECORD",
        "title": "NIRF Rankings",
        "url": "https://en.wikipedia.org/wiki/National_Institutional_Ranking_Framework",
        "snippet": "IIT Madras has been ranked #1 in overall NIRF rankings for 6 consecutive years.",
    }
    with patch.object(SupplementalWebFetcher, "query_supplemental_evidence", return_value=mock_rec):
        ctx = CommandContext(
            query="/browser NIRF Rankings IIT Madras",
            command_name="browser",
            raw_args="NIRF Rankings IIT Madras",
        )
        res = handle_browser_command(ctx)
        assert res.command == "/browser"
        assert res.quality_gate_decision == "accept"
        assert "Audited External Research Evidence" in res.answer
        assert "IIT Madras" in res.answer
        assert len(res.citations) == 1
        assert res.citations[0]["source_type"] == "EXTERNAL_PUBLIC_RECORD"


def test_browser_citation_contract_compliance():
    """Verifies handle_browser_command produces citations strictly adhering to the contract."""
    mock_text = "Harvard University is a private research university established in 1636."
    with patch.object(SupplementalWebFetcher, "fetch_url_text", return_value=mock_text):
        ctx = CommandContext(
            query="/browser https://en.wikipedia.org/wiki/Harvard_University",
            command_name="browser",
            raw_args="https://en.wikipedia.org/wiki/Harvard_University",
        )
        res = handle_browser_command(ctx)
        assert res.command == "/browser"
        assert res.quality_gate_decision == "accept"
        assert len(res.citations) == 1
        cit = res.citations[0]
        assert cit["citation_index"] == 1
        assert cit["source_type"] == "EXTERNAL_PUBLIC_RECORD"
        assert cit["url"].startswith("http://") or cit["url"].startswith("https://")
        assert cit["primary_page"] == 1
        assert cit.get("doc_id") is None
        assert cit.get("filename") is None
        assert cit.get("score") == 0.96
        assert cit["heading"] == "External Web Source - Harvard University"
        assert "Harvard" in cit.get("plain_text", "")
        assert "Harvard" in cit.get("snippet", "")


def test_web_fetcher_html_cleaning():
    """Verifies _clean_html strips tags, scripts, and properly unescapes HTML entities."""
    raw = "<div>Hello &amp; welcome to &quot;RAISE&quot;! <script>alert(1)</script><style>body{color:red}</style></div>"
    cleaned = SupplementalWebFetcher._clean_html(raw)
    assert cleaned == 'Hello & welcome to "RAISE"!'


def test_web_fetcher_url_scheme_validation():
    """Verifies fetch_url_text rejects file://, ftp://, or arbitrary malicious protocols."""
    assert SupplementalWebFetcher.fetch_url_text("file:///etc/passwd") is None
    assert SupplementalWebFetcher.fetch_url_text("ftp://ftp.example.com") is None


def test_browser_url_without_scheme():
    """Verifies /browser automatically infers https:// for www and domain queries."""
    with patch.object(SupplementalWebFetcher, "fetch_url_text", return_value="Wikipedia free encyclopedia content."):
        ctx = CommandContext(
            query="/browser www.wikipedia.org",
            command_name="browser",
            raw_args="www.wikipedia.org",
        )
        res = handle_browser_command(ctx)
        assert res.command == "/browser"
        assert res.quality_gate_decision == "accept"
        assert len(res.citations) == 1
        assert res.citations[0]["url"] == "https://www.wikipedia.org"


def test_web_fetcher_extract_label_strips_extensions():
    """Verifies _extract_label strips .html and .php extensions without truncation."""
    lbl1 = SupplementalWebFetcher._extract_label("https://example.com/research/annual_report.html")
    assert lbl1 == "annual report"
    lbl2 = SupplementalWebFetcher._extract_label("https://example.com/admissions/overview.php")
    assert lbl2 == "overview"
    lbl3 = SupplementalWebFetcher._extract_label("https://en.wikipedia.org/wiki/Stanford_University#History")
    assert lbl3 == "Stanford University"


# ==============================================================================
# 4. Global Dispatcher & Bridge Integration Tests
# ==============================================================================

def test_is_slash_command_heuristic():
    """Verifies is_slash_command accurately classifies queries."""
    assert is_slash_command("/compare") is True
    assert is_slash_command("/audit something") is True
    assert is_slash_command("/browser https://example.com") is True
    assert is_slash_command("What is the revenue?") is False
    assert is_slash_command("//comment") is False
    assert is_slash_command("/") is False


def test_execute_slash_command_global_registry():
    """Verifies execute_slash_command correctly parses and dispatches."""
    res = execute_slash_command(
        raw_query="/compare research",
        active_docs=["UnivA.pdf", "UnivB.pdf"],
    )
    assert res is not None
    assert res.command == "/compare"
    assert res.status == "SUCCESS"
    assert res.execution_time >= 0.0


def test_unknown_command_returns_friendly_error(clean_registry):
    """Verifies typing an unregistered command returns helpful error message."""
    ctx = CommandContext(query="/nonexistent", command_name="nonexistent", raw_args="")
    res = clean_registry.dispatch(ctx)
    assert res.status == "ERROR"
    assert "Unknown command `/nonexistent`" in res.answer
    assert "/help" in res.answer
