"""
Unit Tests for Hypothetical Document Embeddings (HyDE) Generator
================================================================
Validates:
1. Zero-shot synthetic passage drafting with fast cloud routing.
2. In-memory LRU caching for repeated query strings.
3. Graceful fallback to original query on unconfigured router.
4. Composite query expansion formatting.
"""

import pytest
from unittest.mock import MagicMock
from src.retrieval.hyde import HyDEGenerator, get_hyde_generator


@pytest.mark.unit
def test_hyde_singleton():
    """Verifies singleton retrieval returns active instance."""
    inst1 = get_hyde_generator()
    inst2 = get_hyde_generator()
    assert inst1 is inst2
    assert isinstance(inst1, HyDEGenerator)


@pytest.mark.unit
def test_hyde_empty_query():
    """Verifies empty or whitespace queries return empty string without errors."""
    gen = HyDEGenerator()
    assert gen.generate_hypothetical_document("") == ""
    assert gen.generate_hypothetical_document("   ") == ""


@pytest.mark.unit
def test_hyde_fallback_without_router():
    """Verifies that without an LLM router, generator returns the clean query as fallback."""
    gen = HyDEGenerator(provider_router=None)
    # Mock _get_router to return None
    gen._get_router = lambda: None
    result = gen.generate_hypothetical_document("What was the capital expenditure for laboratory upgrades?")
    assert result == "What was the capital expenditure for laboratory upgrades?"


@pytest.mark.unit
def test_hyde_cloud_provider_generation_and_caching():
    """Verifies fast cloud provider generation succeeds and populates cache."""
    mock_router = MagicMock()
    mock_gemini = MagicMock()
    mock_gemini.is_available = True
    mock_gemini.generate.return_value = (
        "In fiscal year 2023-24, capital expenditure on advanced laboratory infrastructure "
        "and scientific instrumentation totaled Rs. 48.50 crore across all central research departments."
    )

    mock_router.get_provider_by_name.side_effect = lambda name: mock_gemini if name == "gemini" else None

    gen = HyDEGenerator(provider_router=mock_router)
    query = "What was the capital expenditure for laboratory upgrades in 2024?"
    passage = gen.generate_hypothetical_document(query)

    assert "Rs. 48.50 crore" in passage
    mock_gemini.generate.assert_called_once()

    # Second call should hit the cache without calling mock_gemini.generate again
    passage2 = gen.generate_hypothetical_document(query)
    assert passage2 == passage
    assert mock_gemini.generate.call_count == 1


@pytest.mark.unit
def test_hyde_composite_query_construction():
    """Verifies construction of expanded search query."""
    mock_router = MagicMock()
    mock_groq = MagicMock()
    mock_groq.is_available = True
    mock_groq.generate.return_value = "Synthetic passage describing patent royalties."
    mock_router.get_provider_by_name.side_effect = lambda name: mock_groq if name == "groq" else None

    gen = HyDEGenerator(provider_router=mock_router)
    expanded = gen.construct_expanded_search_query("Total patent royalties")

    assert "Total patent royalties" in expanded
    assert "[Contextual Blueprint]:" in expanded
    assert "Synthetic passage describing patent royalties." in expanded
