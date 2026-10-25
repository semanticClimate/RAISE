import pytest
from prompts.system_synthesis import sanitize_rag_text

def test_sanitize_rag_text_nominee_list():
    raw_text = """The State Government Nominees listed in the report are:

Thiru. V Arun Roy, IAS
Prof. S Mohan
Dr. Utpal Sharma
Dr. Utpal Sharma is also Principal (BRAIT) cum Vice Chancellor of Puducherry Technological University. Thiru. V Arun Roy, IAS is the Secretary to Government, Industries Department, and Special Secretary (IT) at the Secretariat, Government of Tamil Nadu. Prof. S Mohan is not associated with any additional roles mentioned in the report. [1]"""

    result = sanitize_rag_text(raw_text)

    # Must contain bullet points for each nominee
    assert "• **Thiru. V Arun Roy, IAS**" in result
    assert "• **Prof. S Mohan**" in result
    assert "• **Dr. Utpal Sharma**" in result

    # Must attribute roles to the bullets
    assert "Secretary to Government" in result
    assert "Principal (BRAIT)" in result

    # Must have double newlines before bullets to prevent paragraph collapse
    assert "\n\n• **" in result

def test_sanitize_rag_text_standard_markdown_bullets():
    raw_text = """Key Strategic Initiatives:
- Initiative Alpha: Focuses on renewable energy grid integration. [1]
- Initiative Beta: Focuses on quantum cryptographic protocols. [2]"""

    result = sanitize_rag_text(raw_text)

    assert "• " in result
    assert "\n\n• " in result
    assert "[1]" in result
    assert "[2]" in result


def test_sanitize_rag_text_strips_omitted_passages_commentary():
    raw_text = """NIPGR Plant Genome Center focuses on genomics research. [1]
Excerpts [4] and [5] were omitted because they refer to another institute and are not relevant.
Passages [6] pertain to environmental monitoring and were not used."""

    result = sanitize_rag_text(raw_text)

    assert "genomics research. [1]" in result
    assert "Excerpts [4]" not in result
    assert "Passages [6]" not in result
    assert "were omitted" not in result


def test_filter_entity_mismatches():
    from src.retrieval.fusion import filter_entity_mismatches

    candidates = [
        {"id": "c1", "text": "NIPGR Plant Genome Center incubates 200 plant genome projects.", "pdf_filename": "NIPGR_Report.pdf"},
        {"id": "c2", "text": "External mining institute annual report details mining engineering.", "pdf_filename": "Mining_Institute.pdf"},
        {"id": "c3", "text": "General deep tech venture funding in India.", "pdf_filename": "Tech_Report.pdf"},
    ]

    institutions = {
        "nipgr": ["nipgr", "national institute of plant genome research"],
        "mining": ["mining institute", "mining engineering"],
    }
    filtered = filter_entity_mismatches("What is the mission of NIPGR?", candidates, institutions=institutions)
    ids = [c["id"] for c in filtered]

    assert "c1" in ids
    assert "c3" in ids
    assert "c2" not in ids  # Conflicting institution chunk must be pruned


def test_filter_subgraph_entity_mismatches():
    from src.retrieval.fusion import filter_subgraph_entity_mismatches

    subgraph = {
        "nodes": [
            {"id": "n1", "name": "NIPGR Plant Genome Center", "label": "Institution"},
            {"id": "n2", "name": "Mining Institute", "label": "Institution"},
            {"id": "n3", "name": "Genomics Incubation", "label": "Initiative"},
        ],
        "edges": [
            {"source": "NIPGR Plant Genome Center", "type": "OPERATES", "target": "Genomics Incubation"},
            {"source": "Mining Institute", "type": "DEPT", "target": "Mining"},
        ],
    }

    filtered = filter_subgraph_entity_mismatches("What startups are at NIPGR?", subgraph)
    node_names = [n["name"] for n in filtered["nodes"]]

    assert "NIPGR Plant Genome Center" in node_names
    assert "Genomics Incubation" in node_names
    assert "Mining Institute" not in node_names
    assert len(filtered["edges"]) == 1
    assert filtered["edges"][0]["source"] == "NIPGR Plant Genome Center"

