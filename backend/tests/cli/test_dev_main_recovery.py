"""
Tests execute_iterative_recovery_query:
Verifies trigger condition, bridge extraction from context, Neo4j bridge search, and graceful refusal.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.cli.benchmark_runner import execute_iterative_recovery_query
from src.retrieval.chain_gate import ChainGateResult


@pytest.mark.integration
@pytest.mark.cli
def test_recovery_loop_triggers_on_incomplete_chain():
    """Verifies that an incomplete chain triggers bridge extraction and second-hop retrieval."""
    mock_pipeline = MagicMock()
    
    # Pass 1: Returns chunks with missing bridge
    mock_pipeline.query_subgraph_graphrag.side_effect = [
        {
            "grounded_answer": "Incomplete entity information.",
            "citations": [
                {"chunk_id": "c1", "similarity": 0.45, "primary_page": 2, "text": "Director Dr. S. Raman was appointed in 2024."}
            ],
            "quality_gate_decision": "accept",
        },
        # Pass 2: Returns bridged evidence
        {
            "grounded_answer": "Dr. S. Raman previously directed the Microelectronics Research Center.",
            "citations": [
                {"chunk_id": "c2", "similarity": 0.88, "primary_page": 7, "text": "Microelectronics Research Center directed by Dr. Raman."}
            ],
            "quality_gate_decision": "accept",
        }
    ]

    mock_gate_res = ChainGateResult(
        is_complete=False,
        required_hops=2,
        completed_hops=1,
        discovered_bridge_entity="Dr. S. Raman",
        target_attribute="previous institution",
        status="TRIGGER_RECOVERY",
    )

    with patch("src.cli.benchmark_runner.ChainCompletenessGate") as mock_gate_cls:
        instance = mock_gate_cls.return_value
        instance.evaluate_chain.side_effect = [
            mock_gate_res,
            ChainGateResult(is_complete=True, required_hops=2, completed_hops=2, status="PASSED")
        ]

        res, recovery_meta = execute_iterative_recovery_query(
            pipeline=mock_pipeline,
            query="Where did the current director work before joining?",
            tier=2,
        )

    assert recovery_meta["loop_executed"] is True
    assert recovery_meta["evidence_bridge_entity"] == "Dr. S. Raman"
    assert mock_pipeline.query_subgraph_graphrag.call_count == 2


@pytest.mark.integration
@pytest.mark.cli
def test_recovery_loop_bypassed_when_first_pass_complete():
    """Verifies that complete chains do not trigger the secondary recovery loop."""
    mock_pipeline = MagicMock()
    mock_pipeline.query_subgraph_graphrag.return_value = {
        "grounded_answer": "The budget was 340.5 Rs. Crore [1].",
        "citations": [
            {"chunk_id": "c1", "similarity": 0.92, "primary_page": 3, "text": "Total expenditure was 340.5 Rs. Crore."}
        ],
        "quality_gate_decision": "accept",
    }

    mock_gate_res = ChainGateResult(
        is_complete=True,
        required_hops=1,
        completed_hops=1,
        status="PASSED",
    )

    with patch("src.cli.benchmark_runner.ChainCompletenessGate") as mock_gate_cls:
        instance = mock_gate_cls.return_value
        instance.evaluate_chain.return_value = mock_gate_res

        res, recovery_meta = execute_iterative_recovery_query(
            pipeline=mock_pipeline,
            query="What was the total expenditure?",
            tier=1,
        )

    assert recovery_meta["loop_executed"] is False
    assert mock_pipeline.query_subgraph_graphrag.call_count == 1
