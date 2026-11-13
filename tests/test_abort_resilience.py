import time
import pytest
from src.api.context import (
    ACTIVE_ABORTS,
    ACTIVE_REQUEST_ABORTS,
    SESSION_ABORT_TIMESTAMPS,
    clear_abort,
    is_aborted,
    record_abort,
)


def test_abort_token_lifecycle():
    """Verify that recording an abort works, but clear_abort restores normal query execution."""
    session_id = "test-session-abc"
    request_id_1 = "req-1"
    request_id_2 = "req-2"

    # Initially clean
    clear_abort(session_id, request_id_1)
    clear_abort(session_id, request_id_2)
    assert not is_aborted(session_id, request_id_1)

    # 1. User aborts query 1
    t_abort = time.time()
    record_abort(session_id, request_id_1)
    assert is_aborted(session_id, request_id_1)

    # 2. Query 2 begins on the SAME session: clear_abort is called on new query intake
    clear_abort(session_id, request_id_2)
    assert not is_aborted(session_id, request_id_2), "New query on same session must NOT be aborted after clear_abort"


def test_timestamp_aware_abort():
    """Verify that a session abort only cancels queries started prior to or during the abort, not future queries."""
    session_id = "test-session-ts"
    req_old = "req-old"
    req_new = "req-new"

    t0 = time.time() - 2.0  # started 2 seconds ago
    record_abort(session_id=session_id)  # abort recorded at now (~t0 + 2.0)

    # In-flight old query must be aborted
    assert is_aborted(session_id, req_old, started_at=t0) is True

    # Future query started after the abort must NOT be aborted
    t_future = time.time() + 1.0
    assert is_aborted(session_id, req_new, started_at=t_future) is False


def test_request_id_isolation():
    """Verify that an abort on request_id_A does not impact request_id_B."""
    rid_a = "req-isolated-a"
    rid_b = "req-isolated-b"

    record_abort(request_id=rid_a)
    assert is_aborted(request_id=rid_a) is True
    assert is_aborted(request_id=rid_b) is False

    clear_abort(request_id=rid_a)
    assert is_aborted(request_id=rid_a) is False
