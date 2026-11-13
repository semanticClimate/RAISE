"""
Unit tests for evaluation and embedding improvements across sources 21 to 30:
- Thread-safe singleton embeddings with prompt name support and no random noise fallback
- Nested chunk['metadata'] provenance resolution
- OCR digit guard against converting English words to numbers
- Mini-batched NLI classification with thread safety
- Include=[] ID-only queries during collection deletion
- Scoped vector query fallback enforcement
- Rigorous quality gate validation
- Active document scoping in question generator
"""

import threading
from unittest.mock import MagicMock, patch
import pytest

from src.features.evaluation.models import StructuredEvidence, ClaimVerificationResult, EvaluationReport
from src.features.evaluation.nli_verifier import FineCatNLIVerifier, _NLI_LOCK
from src.features.evaluation.numerical_verifier import NumericalClaimVerifier
from src.features.evaluation.provenance_tracker import ProvenanceTracker
from src.features.evaluation.quality_gate import RigorousQualityGate
from src.features.evaluation.question_generator import DynamicQuestionGenerator
from src.infrastructure.vector.mixins.embeddings_mixin import VectorEmbeddingsMixin, _EMBEDDING_LOCK
from src.infrastructure.vector.mixins.lifecycle_mixin import VectorLifecycleMixin
from src.infrastructure.vector.mixins.search_mixin import VectorSearchMixin


# ---------------------------------------------------------------------------
# 1. Embeddings Mixin Tests
# ---------------------------------------------------------------------------
class DummyVectorEngine(VectorEmbeddingsMixin):
    def __init__(self):
        self.model_key = "google/embeddinggemma-2"
        self.embed_model = None

    @property
    def dimension(self) -> int:
        return 768


def test_embedding_lock_exists():
    assert isinstance(_EMBEDDING_LOCK, type(threading.Lock()))


def test_compute_embeddings_query_prompt_propagation():
    engine = DummyVectorEngine()
    mock_model = MagicMock()
    mock_model.prompts = {"Retrieval-query": "task: search query", "Retrieval-document": "task: doc"}
    mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.1] * 768])

    with patch.object(engine, "_get_embedding_model", return_value=mock_model):
        res = engine.compute_embeddings(["test query"], is_query=True)
        assert len(res) == 1
        assert len(res[0]) == 768
        mock_model.encode.assert_called_once()
        kwargs = mock_model.encode.call_args[1]
        assert kwargs.get("prompt_name") == "Retrieval-query"


def test_compute_embeddings_document_prompt_propagation():
    engine = DummyVectorEngine()
    mock_model = MagicMock()
    mock_model.prompts = {"Retrieval-query": "task: search query", "Retrieval-document": "task: doc"}
    mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.1] * 768])

    with patch.object(engine, "_get_embedding_model", return_value=mock_model):
        res = engine.compute_embeddings(["test doc"], is_query=False)
        assert len(res) == 1
        kwargs = mock_model.encode.call_args[1]
        assert kwargs.get("prompt_name") == "Retrieval-document"


def test_compute_embeddings_raises_on_failure_no_random_poison():
    engine = DummyVectorEngine()
    with patch.object(engine, "_get_embedding_model", return_value=None):
        with pytest.raises(RuntimeError, match="not available"):
            engine.compute_embeddings(["fail text"])


# ---------------------------------------------------------------------------
# 2. Provenance Tracker Tests (Nested Metadata Extraction)
# ---------------------------------------------------------------------------
def test_provenance_tracker_resolves_nested_metadata():
    chunks = [
        {
            "chunk_id": "top_chunk_1",
            "metadata": {
                "primary_page": "4",
                "source_pages": [4, 5],
                "pdf_filename": "AnnualReport.pdf",
                "text": "Deep Learning innovations at IIT Madras.",
            },
        }
    ]

    prov = ProvenanceTracker.resolve_chunk_provenance(1, chunks)
    assert prov is not None
    assert prov["chunk_id"] == "top_chunk_1"
    assert 4 in prov["pages"]
    assert 5 in prov["pages"]
    assert prov["document"] == "AnnualReport.pdf"
    assert "Deep Learning" in prov["text"]


def test_provenance_tracker_resolves_printed_page():
    chunks = [
        {
            "citation_index": 1,
            "metadata": {
                "printed_page": "12",
                "document_id": "DocA.pdf",
            },
            "plain_text": "Sample text",
        }
    ]
    prov = ProvenanceTracker.resolve_chunk_provenance(1, chunks)
    assert prov is not None
    assert 12 in prov["pages"]
    assert prov["document"] == "DocA.pdf"


# ---------------------------------------------------------------------------
# 3. Numerical Verifier Tests (OCR Digit Guard)
# ---------------------------------------------------------------------------
def test_numerical_verifier_rejects_english_words():
    # "School", "Council", "Social" should NOT be extracted as numbers
    text = "The School Council met to discuss the Social fund."
    nums = NumericalClaimVerifier.extract_numbers(text)
    assert "School" not in nums
    assert "Council" not in nums
    assert "Social" not in nums
    # All extracted tokens should be valid numbers
    for n in nums:
        cleaned = n.replace(",", "").replace("$", "").replace("₹", "")
        assert any(c.isdigit() for c in cleaned)


def test_numerical_verifier_accepts_real_numbers_and_currency():
    text = "The application fee was 2000.0 INR and the total grant was 15,000 USD."
    nums = NumericalClaimVerifier.extract_numbers(text)
    assert any("2000" in n for n in nums)
    assert any("15,000" in n or "15000" in n for n in nums)


# ---------------------------------------------------------------------------
# 4. NLI Verifier Mini-Batching & Lock Tests
# ---------------------------------------------------------------------------
def test_nli_lock_exists():
    assert isinstance(_NLI_LOCK, type(threading.Lock()))


def test_nli_verifier_batch_chunking():
    verifier = FineCatNLIVerifier()
    pairs = [("Premise text", f"Hypothesis claim {i}") for i in range(20)]

    import torch
    mock_tok = MagicMock()
    mock_model = MagicMock()

    # Pass the actual batch length through the tokenizer mock
    def fake_tok(premises, hypotheses, **kw):
        mock_inputs = MagicMock()
        mock_inputs.__len__ = lambda self: len(premises)
        mock_inputs.to = lambda dev: {"batch_len": len(premises)}
        return mock_inputs

    mock_tok.side_effect = fake_tok

    def fake_forward(**inputs):
        blen = inputs.get("batch_len", 8)
        return MagicMock(logits=torch.tensor([[0.1, 0.1, 0.8]] * blen))

    mock_model.side_effect = fake_forward

    with patch("src.features.evaluation.nli_verifier._CACHED_MODEL", mock_model), \
         patch("src.features.evaluation.nli_verifier._CACHED_TOKENIZER", mock_tok), \
         patch("src.features.evaluation.nli_verifier._CACHED_DEVICE", "cpu"), \
         patch.object(verifier, "_ensure_loaded", return_value=True):
        results = verifier.classify_batch(pairs)
        assert len(results) == 20
        # 20 pairs / batch_size=8 -> 3 forward calls (8 + 8 + 4)
        assert mock_model.call_count == 3


# ---------------------------------------------------------------------------
# 5. Lifecycle Mixin Include=[] Tests
# ---------------------------------------------------------------------------
class DummyLifecycleEngine(VectorLifecycleMixin):
    def __init__(self):
        self.collection = MagicMock()


def test_lifecycle_delete_passes_include_empty():
    engine = DummyLifecycleEngine()
    engine.collection.get.return_value = {"ids": ["chunk_1", "chunk_2"]}

    engine.delete_document("test.pdf", doc_id="doc_123")
    # Verify every call to collection.get passed include=[]
    for call in engine.collection.get.call_args_list:
        assert call[1].get("include") == []


# ---------------------------------------------------------------------------
# 6. Search Mixin Scoped Query Fallback Tests
# ---------------------------------------------------------------------------
class DummySearchEngine(VectorSearchMixin):
    def __init__(self):
        self._collection = MagicMock()

    @property
    def dimension(self) -> int:
        return 768

    def count(self) -> int:
        return 10

    def format_query_for_embedding(self, q):
        return q

    def compute_embeddings(self, texts, is_query=False):
        return [[0.1] * 768 for _ in texts]

    def _get_collection(self):
        return self._collection


def test_search_mixin_blocks_global_fallback_when_where_clause_active():
    engine = DummySearchEngine()
    col = engine._collection
    # First scoped query returns no hits
    col.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    # Search with active_docs specified
    res = engine.search("What is the grant?", top_k=5, active_docs=["SpecificDoc.pdf"])
    assert res == []
    # Verify col.query was called only ONCE (scoped attempt), NOT followed by unscoped global query
    assert col.query.call_count == 1
    call_kwargs = col.query.call_args[1]
    assert "where" in call_kwargs


# ---------------------------------------------------------------------------
# 7. Quality Gate Validation Tests
# ---------------------------------------------------------------------------
def test_quality_gate_validate_with_guardrails():
    gate = RigorousQualityGate()
    # Response too short
    short_res = gate.validate_with_guardrails("Too short", ["Context passage here"])
    assert short_res["valid"] is False
    assert "too short" in short_res["reason"].lower()

    # Grounded response with lexical overlap
    valid_res = gate.validate_with_guardrails(
        "The application fee was 2000 INR for the candidate examination.",
        ["The candidate must pay an application fee of 2000 INR for the examination."]
    )
    assert valid_res["valid"] is True
    assert valid_res["method"] == "core-quality-gate"


# ---------------------------------------------------------------------------
# 8. Question Generator Scoping Tests
# ---------------------------------------------------------------------------
def test_question_generator_active_docs_scoping(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir(parents=True)

    # File A
    file_a = chunks_dir / "annualreport_chunks.json"
    file_a.write_text('[{"university": "IIT Madras", "heading": "Incubation Growth", "plain_text": "Grant was 50 Crore"}]', encoding="utf-8")

    # File B
    file_b = chunks_dir / "gateform_chunks.json"
    file_b.write_text('[{"university": "GATE 2024", "heading": "Candidate Details", "plain_text": "Fee was 2000 INR"}]', encoding="utf-8")

    generator = DynamicQuestionGenerator(processed_dir=tmp_path)
    # Scoped only to gateform
    questions = generator.generate_smart_questions(max_questions=4, active_docs=["gateform.pdf"])
    assert len(questions) > 0
    # Questions should reflect GATE 2024 or Candidate Details, not IIT Madras
    assert any("GATE" in q or "Candidate" in q or "Fee" in q for q in questions)
    assert not any("IIT Madras" in q for q in questions)
