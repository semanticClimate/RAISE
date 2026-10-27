"""
Sessions & Chat History Router
Endpoints for conversation persistence, message trajectory, drawer synchronization, and session lifecycle.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from src.api.context import _parse_drawer_active_docs
from src.api.dependencies import (
    get_postgres_manager,
    get_redis_cache,
    get_session_memory,
    get_rag_engine,
    get_session_service,
)
from src.api.schemas import ChatHistorySyncRequest

logger = logging.getLogger("raise.router.sessions")
router = APIRouter(tags=["Sessions & History"])


@router.get("/api/chat/history")
async def get_chat_history_spec(
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    limit: int = 50,
    session_service: Any = Depends(get_session_service),
):
    """
    Tier 1 Critical: Retrieve persistent chronological message turns from PostgreSQL.
    CRITICAL: Never return [] on DB connection errors; raise HTTP 503 so frontend preserves cache.
    """
    target_id = session_id or thread_id or "default"
    try:
        res = session_service.get_chat_history(target_id, limit=limit)
        if isinstance(res, dict) and "messages" in res and isinstance(res["messages"], list):
            for m in res["messages"]:
                if isinstance(m, dict):
                    txt = m.get("text") or m.get("content", "")
                    m["text"] = txt
                    m["content"] = txt
        return res
    except Exception as exc:
        logger.error(f"Error retrieving chat history for {target_id}: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unreachable. Preserving client cache."
        )


@router.post("/api/chat/history")
async def save_chat_history_spec(
    payload: ChatHistorySyncRequest,
    session_service: Any = Depends(get_session_service),
):
    """
    Tier 1 Critical: Idempotently synchronize or save client session history into PostgreSQL.
    Prevents duplicate turns while preserving message ordering, timestamps, and citations.
    """
    target_id = payload.session_id or payload.thread_id or "default"
    attached = payload.attached_docs or payload.selectedSourceIds
    normalized_messages = []
    for m in (payload.messages or []):
        if isinstance(m, dict):
            txt = m.get("text") or m.get("content", "")
            m["text"] = txt
            m["content"] = txt
            normalized_messages.append(m)
        else:
            normalized_messages.append(m)
    try:
        return session_service.sync_chat_history(
            session_id=target_id,
            messages=normalized_messages,
            title=payload.title,
            attached_docs=attached,
        )
    except Exception as exc:
        logger.error(f"Error synchronizing chat history for {target_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/chat/sessions")
async def get_chat_sessions_spec(session_service: Any = Depends(get_session_service)):
    """
    Tier 1 Critical: List all chat sessions, titles, created timestamps, and message counts from PostgreSQL.
    CRITICAL: Never return [] on DB connection errors; raise HTTP 503 so frontend preserves cache.
    """
    try:
        return session_service.list_sessions()
    except Exception as exc:
        logger.error(f"PostgreSQL session query failure: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unreachable. Preserving client cache."
        )


@router.delete("/api/chat/sessions/{thread_id}")
async def delete_chat_session_spec(
    thread_id: str,
    session_service: Any = Depends(get_session_service),
):
    """
    Tier 1 Critical: Delete a session and its message logs from PostgreSQL and memory.
    """
    return session_service.delete_session(thread_id)


@router.post("/api/chat/sessions/{session_id}/rename")
@router.patch("/api/chat/sessions/{session_id}/rename")
async def rename_chat_session_spec(
    session_id: str,
    payload: Dict[str, Any] = Body(...),
    session_service: Any = Depends(get_session_service),
):
    """
    Tier 1 Critical: Rename session title in PostgreSQL and cache.
    Accepts: { "title": "New Title" } or { "new_title": "New Title" } or { "name": "New Title" }
    """
    new_title = payload.get("title") or payload.get("new_title") or payload.get("name")
    if not new_title or not str(new_title).strip():
        raise HTTPException(status_code=400, detail="Missing or empty 'title' in payload")
    return session_service.rename_session(session_id, str(new_title).strip())



@router.get("/api/chat/sessions/{session_id}/drawer")
async def get_session_drawer_endpoint(
    session_id: str,
    session_service: Any = Depends(get_session_service),
):
    """
    Dedicated Drawer GET endpoint:
    Returns the authoritative list of attached documents for a given session/chat ID,
    including enriched metadata for each attached document.
    """
    return session_service.get_session_drawer(session_id)



@router.post("/api/chat/sessions/{session_id}/drawer/attach")
async def attach_to_session_drawer_endpoint(
    session_id: str,
    payload: Dict[str, Any] = Body(...),
    session_service: Any = Depends(get_session_service),
):

    """
    Dedicated Drawer Attach endpoint:
    Idempotently attaches a Library document to the current session's Drawer.
    Accepts: { "document_id": "..." } or { "filename": "..." } or { "document": "..." }
    """
    target = payload.get("filename") or payload.get("document_id") or payload.get("document") or payload.get("doc_id")
    if not target:
        raise HTTPException(status_code=400, detail="Missing 'filename', 'document_id', or 'document' in payload")
    return session_service.attach_document_to_drawer(session_id, target)


@router.post("/api/chat/sessions/{session_id}/drawer/remove")
async def remove_from_session_drawer_endpoint(
    session_id: str,
    payload: Dict[str, Any] = Body(...),
    session_service: Any = Depends(get_session_service),
):
    """
    Dedicated Drawer Remove endpoint:
    Removes a document from the current session's Drawer.
    Does NOT delete the document from the Library.
    Accepts: { "document_id": "..." } or { "filename": "..." } or { "document": "..." }
    """
    target = payload.get("filename") or payload.get("document_id") or payload.get("document") or payload.get("doc_id")
    if not target:
        raise HTTPException(status_code=400, detail="Missing 'filename', 'document_id', or 'document' in payload")
    return session_service.remove_document_from_drawer(session_id, target)


@router.patch("/api/chat/sessions/{session_id}/drawer")
@router.put("/api/chat/sessions/{session_id}/drawer")
async def update_session_drawer_spec(
    session_id: str,
    payload: Dict[str, Any] = Body(...),
    session_service: Any = Depends(get_session_service),
):
    """
    Tier 1 Critical: Persist attached drawer documents for a given session.
    Enables automatic drawer rehydration when the user switches sessions in the sidebar.
    """
    docs = payload.get("active_docs", payload.get("attached_docs", []))
    cleaned_docs = _parse_drawer_active_docs(docs) or []
    return session_service.update_session_drawer(session_id, cleaned_docs)



@router.get("/api/session/{session_id}/history")
async def get_session_history(
    session_id: str,
    postgres_manager: Any = Depends(get_postgres_manager),
    redis_cache: Any = Depends(get_redis_cache),
    session_memory_manager: Any = Depends(get_session_memory),
):
    """Retrieve checkpointed conversational turns and active entities for a session."""
    turns = session_memory_manager.get_thread_history(session_id) if session_memory_manager else []
    pg_msgs = postgres_manager.get_messages(session_id, limit=50) if postgres_manager else []
    session_vars = redis_cache.get_session_memory(session_id) if redis_cache else {}

    normalized_pg = []
    for m in pg_msgs:
        txt = m.get("text") or m.get("content", "")
        m["content"] = txt
        m["text"] = txt
        normalized_pg.append(m)

    normalized_turns = []
    for t in turns:
        td = t.to_dict() if hasattr(t, "to_dict") else dict(t)
        txt = td.get("text") or td.get("content") or td.get("user_query") or td.get("assistant_response", "")
        td["content"] = txt
        td["text"] = txt
        normalized_turns.append(td)

    return {
        "session_id": session_id,
        "turns_count": len(normalized_pg) or len(normalized_turns),
        "history": normalized_turns if normalized_turns else normalized_pg,
        "messages": normalized_pg,
        "memory_vars": session_vars,
    }


@router.delete("/api/session/{session_id}")
async def clear_session_history(
    session_id: str,
    postgres_manager: Any = Depends(get_postgres_manager),
    redis_cache: Any = Depends(get_redis_cache),
    session_memory_manager: Any = Depends(get_session_memory),
):
    """Clear memory checkpoint and conversation state across Redis, PostgreSQL, and in-memory engine."""
    if session_memory_manager:
        session_memory_manager.clear_thread(session_id)
    if postgres_manager:
        postgres_manager.clear_session(session_id)
    if redis_cache:
        redis_cache.clear_session_messages(session_id)
    return {"status": "success", "session_id": session_id, "message": "Session history cleared."}


@router.post("/api/chat/delete")
@router.delete("/api/chat/delete")
@router.post("/api/chat/clear")
@router.delete("/api/chat/clear")
@router.delete("/api/chat/history")
@router.delete("/api/history")
async def clear_chat(
    request: Request,
    postgres_manager: Any = Depends(get_postgres_manager),
    session_memory_manager: Any = Depends(get_session_memory),
    rag_engine: Any = Depends(get_rag_engine),
):
    """Clear conversational trajectory and reasoning memory."""
    try:
        session_id = request.query_params.get("session_id") or request.query_params.get("thread_id")
        confirm = request.query_params.get("confirm", "").lower() in ("true", "1", "yes")
        if not session_id:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    session_id = body.get("session_id") or body.get("thread_id")
                    if not confirm:
                        confirm = body.get("confirm") is True or str(body.get("confirm", "")).lower() in ("true", "1", "yes")
            except Exception:
                pass

        if session_id:
            if session_memory_manager and hasattr(session_memory_manager, "_threads"):
                session_memory_manager._threads.pop(session_id, None)
            if postgres_manager:
                postgres_manager.clear_session(session_id)
            return {"status": "success", "message": f"Session '{session_id}' cleared successfully"}

        # Require explicit confirmation before clearing all sessions across all users
        if not confirm:
            raise HTTPException(
                status_code=400,
                detail="Confirmation required to clear all chat sessions. Pass 'confirm=true' or specify a 'session_id'."
            )

        if session_memory_manager and hasattr(session_memory_manager, "_threads"):
            session_memory_manager._threads.clear()
        if postgres_manager and hasattr(postgres_manager, "clear_all_sessions"):
            postgres_manager.clear_all_sessions()
        if rag_engine:
            rag_engine.clear_chat_session()
        return {"status": "success", "message": "All chat sessions cleared successfully"}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}
