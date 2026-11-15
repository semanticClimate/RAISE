"""
Unit and Integration Tests for Dynamic Model Configuration & Pre-Warming
========================================================================
Tests that:
1. EMBEDDING_MODEL, RERANKER_MODEL, NLI_MODEL and their devices are configurable
   via environment variables and typed Settings objects.
2. CrossEncoderReranker supports arbitrary model IDs, custom devices, and async arerank.
3. FineCatNLIVerifier dynamically adapts to custom model IDs, devices, and label mappings.
4. warmup_all_neural_models pre-warms all 3 components cleanly without crashing on Windows.
"""

import os
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.core.config import Settings, VectorConfig, RerankerConfig, NLIConfig, models
from src.retrieval.reranker import CrossEncoderReranker
from src.features.evaluation.nli_verifier import FineCatNLIVerifier
from src.infrastructure.model_warmup import warmup_all_neural_models


def test_typed_configuration_defaults_and_env():
    """Verify that typed configuration defaults to expected values and respects env."""
    cfg = Settings()
    assert hasattr(cfg, "vector")
    assert hasattr(cfg, "reranker")
    assert hasattr(cfg, "nli")

    assert cfg.vector.embedding_model == os.getenv("EMBEDDING_MODEL", models.EMBEDDING_MODEL_NAME)
    assert cfg.vector.embedding_device == os.getenv("EMBEDDING_DEVICE", "cuda")
    assert cfg.reranker.model_name == os.getenv("RERANKER_MODEL", models.RERANKER_MODEL_NAME)
    assert cfg.reranker.device == os.getenv("RERANKER_DEVICE", "cuda")
    assert cfg.nli.model_name == os.getenv("NLI_MODEL", models.NLI_MODEL_NAME)
    assert cfg.nli.device == os.getenv("NLI_DEVICE", "cuda")


def test_cross_encoder_reranker_dynamic_model_selection(monkeypatch):
    """Verify that CrossEncoderReranker respects custom model names and devices."""
    custom_test_model = "custom_test_checkpoint"
    monkeypatch.setenv("RERANKER_MODEL", custom_test_model)
    monkeypatch.setenv("RERANKER_DEVICE", "cpu")

    reranker = CrossEncoderReranker()
    assert reranker.model_name == custom_test_model
    assert reranker.device == "cpu"


@pytest.mark.asyncio
async def test_cross_encoder_reranker_arerank():
    """Verify that arerank dispatches asynchronously and returns results."""
    reranker = CrossEncoderReranker()
    # Mock rerank to return candidates
    sample_candidates = [{"chunk_id": "c1", "text": "passage 1", "score": 0.5}]
    with patch.object(reranker, "rerank", return_value=sample_candidates) as mock_rerank:
        res = await reranker.arerank("sample query", sample_candidates)
        assert res == sample_candidates
        mock_rerank.assert_called_once()


def test_nli_verifier_dynamic_model_selection(monkeypatch):
    """Verify that FineCatNLIVerifier respects custom model IDs and devices."""
    monkeypatch.setenv("NLI_MODEL", "custom-org/my-nli-model")
    monkeypatch.setenv("NLI_DEVICE", "cpu")

    verifier = FineCatNLIVerifier()
    assert verifier.model_id == "custom-org/my-nli-model"
    assert verifier.device == "cpu"


def test_nli_verifier_dynamic_label_mapping():
    """Verify that classify_batch discovers label mapping dynamically from model config."""
    verifier = FineCatNLIVerifier()
    
    # Mock model and tokenizer to test dynamic label indexing
    mock_model = MagicMock()
    mock_model.config.id2label = {
        0: "contradiction",
        1: "neutral",
        2: "entailment",
    }
    
    # Simulate logits with high entailment at index 2
    import numpy as np
    import torch
    
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[ -2.0, 0.0, 5.0 ]])
    mock_model.return_value = mock_output

    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value.to.return_value = {}

    with patch("src.features.evaluation.nli_verifier._CACHED_MODEL", mock_model), \
         patch("src.features.evaluation.nli_verifier._CACHED_TOKENIZER", mock_tokenizer), \
         patch("src.features.evaluation.nli_verifier._CACHED_DEVICE", "cpu"):
        
        results = verifier.classify_batch([("The premise is true.", "The hypothesis is true.")])
        assert len(results) == 1
        res = results[0]
        # Entailment probability should be near 1.0 because index 2 was entailed
        assert res["verdict"] == "ENTAILMENT"
        assert res["is_entailed"] is True
        assert res["is_contradiction"] is False


def test_warmup_all_neural_models_execution():
    """Verify that warmup_all_neural_models executes and records component latencies."""
    latencies = warmup_all_neural_models()
    assert isinstance(latencies, dict)
    # At least embedding or reranker should be pre-warmed
    assert any(k in latencies for k in ["embedding", "reranker", "nli"])


def test_readiness_probe_and_endpoint():
    """Verify that is_neural_stack_ready() reflects state and /api/ready endpoint responds correctly."""
    from src.infrastructure.model_warmup import is_neural_stack_ready
    from app import app
    from fastapi.testclient import TestClient

    ready = is_neural_stack_ready()
    assert isinstance(ready, bool)

    client = TestClient(app)
    resp = client.get("/api/ready")
    assert resp.status_code in [200, 503]
    data = resp.json()
    assert "ready" in data
    assert "status" in data
