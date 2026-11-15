import pytest
from unittest.mock import patch, MagicMock
from src.core.config import models
from src.infrastructure.vector.mixins.embeddings_mixin import VectorEmbeddingsMixin
from src.infrastructure.cache.semantic_cache import SemanticCacheMixin


class DummyVectorEngine(VectorEmbeddingsMixin):
    def __init__(self):
        self._dimension = 768
        self.model_path = models.EMBEDDING_MODEL_NAME
        self.embed_model = None
        self.AVAILABLE_MODELS = {models.EMBEDDING_MODEL_NAME: models.EMBEDDING_MODEL_NAME}


class DummySemanticCache(SemanticCacheMixin):
    def __init__(self):
        self.is_connected = False
        self._client = None
        self._memory_semantic_cache = {}

    def get_completion(self, query, mode, library=None, active_docs=None):
        return None

    def set_completion(self, query, mode, data, library=None, active_docs=None, ttl=86400):
        pass


def test_embedding_model_safe_fallback_on_early_import_error():
    """Verify that early exceptions inside _get_embedding_model do not raise UnboundLocalError."""
    engine = DummyVectorEngine()
    
    # Simulate an error on import of sentence_transformers
    with patch.dict("sys.modules", {"sentence_transformers": None}):
        # Should not throw UnboundLocalError: raw_id or dev
        try:
            model = engine._get_embedding_model()
            # It may return None or a fallback if sentence_transformers cannot load
            assert model is None or hasattr(model, "encode")
        except UnboundLocalError as ule:
            pytest.fail(f"UnboundLocalError raised: {ule}")
        except Exception:
            # Other handled exceptions are acceptable, but UnboundLocalError must NEVER be raised
            pass


def test_semantic_cache_scope_isolation():
    """Verify that semantically identical queries under different active_docs scopes do NOT cross-contaminate."""
    cache = DummySemanticCache()
    
    query = "What is the qualifying exam score?"
    embedding = [0.1] * 768
    data_doc_a = {"answer": "Score for Document A is 85"}
    data_doc_b = {"answer": "Score for Document B is 92"}

    # Store entry for Document A
    cache.semantic_set(
        query=query,
        result=data_doc_a,
        mode="fast",
        embedding=embedding,
        library="default",
        active_docs=["DocA.pdf"],
    )

    # 1. Lookup with DocA.pdf should HIT
    hit_a = cache.semantic_get(
        query=query,
        mode="fast",
        embedding=embedding,
        threshold=0.95,
        library="default",
        active_docs=["DocA.pdf"],
    )
    assert hit_a is not None
    assert hit_a.get("answer") == "Score for Document A is 85"

    # 2. Lookup with DocB.pdf MUST NOT return DocA's answer!
    hit_b = cache.semantic_get(
        query=query,
        mode="fast",
        embedding=embedding,
        threshold=0.95,
        library="default",
        active_docs=["DocB.pdf"],
    )
    assert hit_b is None, "Cross-document cache contamination! Returned answer from DocA for DocB query."

    # 3. Lookup with empty scope MUST NOT return DocA's answer
    hit_global = cache.semantic_get(
        query=query,
        mode="fast",
        embedding=embedding,
        threshold=0.95,
        library="default",
        active_docs=[],
    )
    assert hit_global is None, "Global query returned document-scoped answer."
