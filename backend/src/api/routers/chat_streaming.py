"""
RAISE Real-Time Chat Streaming & Generator Engine
================================================
Component: `src.api.routers.chat_streaming`
Architecture Layer: API Gateway / Streaming & Transport Layer

Overview:
---------
This module encapsulates asynchronous streaming generators and HTTP streaming
responses for the RAISE Chat API.

Supported Streaming Formats:
1. Server-Sent Events (SSE - `text/event-stream`):
   - Emits structured `data: {"token": "..."}` payloads with keepalive comments.
   - Respects client disconnects and real-time cancellation tokens (`/api/chat/abort`).
   - Dispatches a terminal completion payload containing citation metadata, source references,
     graph subgraphs, and quality gate results.
2. Raw Plain-Text Streaming (`text/plain`):
   - Directly streams word/token chunks for zero-overhead frontends or CLI consumers
     without requiring JSON event parsing.
3. Cached Stream Delivery:
   - Plays back cached query answers at low latency while emulating natural typing cadences.
4. Empty Drawer Guard Responses:
   - Delivers immediate polite instruction when active drawer context is missing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

try:
    from prompts.system_synthesis import sanitize_rag_text
except ImportError:
    from RAG.prompts.system_synthesis import sanitize_rag_text

from src.api.context import is_aborted, record_query_metric
from src.api.schemas import ChatMessageRequest

logger = logging.getLogger("raise.router.chat.streaming")


def _normalize_quality_gate_decision(val: Any) -> str:
    """Normalizes decision to: 'accept' | 'retry' | 'unable_to_verify' | 'empty_workspace'."""
    s = str(val or "accept").lower().strip()
    if s in ("accept", "active", "pass", "passed", "success"):
        return "accept"
    if s == "retry":
        return "retry"
    if s in ("empty_workspace", "empty_drawer", "no_docs"):
        return "empty_workspace"
    return "unable_to_verify"


def create_empty_drawer_raw_stream(
    reply: str,
    request: Request,
    rate_headers: Dict[str, str],
) -> StreamingResponse:
    """Deliver an immediate plain-text stream when no drawer documents are attached."""
    async def fast_raw_stream():
        words = re.findall(r"\S+|\s+", reply)
        for w in words:
            if await request.is_disconnected():
                return
            yield w
            await asyncio.sleep(0.015)

    return StreamingResponse(
        fast_raw_stream(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", **rate_headers},
    )


def create_empty_drawer_sse_stream(
    reply: str,
    request: Request,
    mode: str,
    session_id: str,
    rate_headers: Dict[str, str],
) -> StreamingResponse:
    """Deliver an immediate SSE event stream when no drawer documents are attached."""
    async def fast_sse_stream():
        yield ": keepalive\n\n"
        words = re.findall(r"\S+|\s+", reply)
        for w in words:
            if await request.is_disconnected():
                return
            yield f"data: {json.dumps({'token': w})}\n\n"
            await asyncio.sleep(0.015)

        meta_payload = {
            "status": "SUCCESS",
            "query": "",
            "answer": reply,
            "thread_id": session_id,
            "session_id": session_id,
            "citations": [],
            "suggestions": [],
            "reply": reply,
            "grounded_answer": reply,
            "sources": [],
            "verified_claims": [],
            "subgraph": {"nodes": [], "edges": []},
            "quality_gate_decision": "accept",
            "traceability_score": 0.95,
            "mode_used": mode,
            "persisted": bool(session_id is not None),
            "saved": bool(session_id is not None),
            "persistence_status": "saved" if session_id else "ephemeral",
            "persistence_error": None,
        }
        yield f"data: {json.dumps(meta_payload)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        fast_sse_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", **rate_headers},
    )


def create_cached_sse_stream(
    cached: Dict[str, Any],
    request: Request,
    session_id: str,
    request_id: str,
    rate_headers: Dict[str, str],
) -> StreamingResponse:
    """Stream cached answer tokens via SSE with keepalives and abort detection."""
    async def cached_sse_stream():
        yield ": keepalive\n\n"
        cached_ans = cached.get("answer") or cached.get("reply") or cached.get("grounded_answer") or ""
        words = re.findall(r"\S+|\s+", cached_ans)
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            if await request.is_disconnected() or is_aborted(session_id, request_id):
                return
            token_chunk = "".join(words[i:i + chunk_size])
            yield f"event: token\ndata: {json.dumps({'token': token_chunk})}\n\n"
            await asyncio.sleep(0.008)

        cits = cached.get("citations", []) or []
        cached_suggestions = cached.get("suggestions") or cached.get("follow_up_inquiries", []) or []
        meta_out = {
            'status': cached.get('status', 'SUCCESS'),
            'query': cached.get('query', ''),
            'answer': cached_ans,
            'thread_id': session_id,
            'session_id': session_id,
            'citations': cits,
            'suggestions': cached_suggestions,
            'sources': cached.get('sources', []),
            'follow_up_inquiries': cached_suggestions,
            'subgraph': cached.get('subgraph', {'nodes': [], 'edges': []}),
            'quality_gate_decision': cached.get('quality_gate_decision', 'accept'),
            'traceability_score': cached.get('traceability_score', 0.95),
            'command': cached.get('command'),
            'verified_claims': cached.get('verified_claims', []),
            'top_chunks': cached.get('top_chunks', []),
            'execution_time': cached.get('execution_time', 0.0),
        }
        yield f"data: {json.dumps(meta_out)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        cached_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Redis-Cache": "HIT",
            **rate_headers,
        },
    )


def create_chat_raw_stream(
    rag_engine: Any,
    message: str,
    req: ChatMessageRequest,
    mode: str,
    session_id: str,
    request_id: str,
    request: Request,
    postgres_manager: Any,
    rate_headers: Dict[str, str],
) -> StreamingResponse:
    """Executes GraphRAG pipeline and streams raw text chunks directly to the response."""
    async def chat_raw_generator():
        t_start = time.perf_counter()
        try:
            rag_task = asyncio.create_task(
                asyncio.to_thread(
                    rag_engine.query_subgraph_graphrag,
                    query=message,
                    hops=req.hops or (1 if mode == "fast" else 2),
                    top_k=req.top_k or (4 if mode == "fast" else 8),
                    document_filter=req.document_filter,
                    active_docs=req.active_docs,
                    mode=mode,
                    thread_id=session_id,
                    chat_history=req.chat_history,
                )
            )

            while not rag_task.done():
                done, _ = await asyncio.wait([rag_task], timeout=2.0)
                if rag_task in done:
                    break
                if await request.is_disconnected() or is_aborted(session_id, request_id):
                    logger.info("Client disconnected or aborted while waiting for GraphRAG query: session=%s, req=%s", session_id, request_id)
                    yield f"data: {json.dumps({'error': {'code': 'CANCELLED', 'message': 'Request cancelled by user'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                yield ": keepalive\n\n"

            result = rag_task.result()
            elapsed = round(time.perf_counter() - t_start, 3)
            record_query_metric(elapsed, success=True)
            raw_ans = result.get("grounded_answer") or result.get("answer", "")
            answer = sanitize_rag_text(str(raw_ans))
            sources = []
            for c in result.get("citations", []):
                fn = c.get("pdf_filename") or (
                    c.get("metadata", {}).get("pdf_filename") if isinstance(c, dict) else None
                )
                if fn and fn not in sources:
                    sources.append(fn)
            if not sources and result.get("source_documents"):
                sources = result.get("source_documents")

            words = re.findall(r"\S+|\s+", answer)
            chunk_size = 6
            for i in range(0, len(words), chunk_size):
                if await request.is_disconnected() or is_aborted(session_id, request_id):
                    logger.info("Client disconnected or aborted: session=%s, req=%s", session_id, request_id)
                    yield " [Request Cancelled]"
                    return
                token_chunk = "".join(words[i:i + chunk_size])
                yield token_chunk
                await asyncio.sleep(0.002)

            if session_id and postgres_manager:
                postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                postgres_manager.save_message(session_id, "assistant", answer, mode=mode, sources=sources)
        except Exception as exc:
            yield f"\n[Error: {str(exc)}]"

    return StreamingResponse(
        chat_raw_generator(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            **rate_headers,
        },
    )


def create_chat_sse_stream(
    rag_engine: Any,
    message: str,
    req: ChatMessageRequest,
    mode: str,
    session_id: str,
    request_id: str,
    library: Optional[str],
    query_embedding: Optional[List[float]],
    request: Request,
    postgres_manager: Any,
    redis_cache: Any,
    rate_headers: Dict[str, str],
) -> StreamingResponse:
    """Executes GraphRAG pipeline and streams SSE events with abort token checking and final metadata payload."""
    async def chat_sse_generator():
        t_start = time.perf_counter()
        yield ": keepalive\n\n"
        if await request.is_disconnected() or is_aborted(session_id, request_id):
            yield f"event: error\ndata: {json.dumps({'error': {'code': 'CANCELLED', 'message': 'Request cancelled by user', 'request_id': request_id}})}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            yield f"event: stage\ndata: {json.dumps({'stage': 'QUERY_INTAKE', 'node': 'query_intake', 'status': 'active', 'detail': 'Analyzing research query intent & resolving entities'})}\n\n"

            rag_task = asyncio.create_task(
                asyncio.to_thread(
                    rag_engine.query_subgraph_graphrag,
                    query=message,
                    hops=req.hops or (1 if mode == "fast" else 2),
                    top_k=req.top_k or (4 if mode == "fast" else 8),
                    document_filter=req.document_filter,
                    active_docs=req.active_docs,
                    mode=mode,
                    thread_id=session_id,
                    chat_history=req.chat_history,
                )
            )

            while not rag_task.done():
                done, _ = await asyncio.wait([rag_task], timeout=2.0)
                if rag_task in done:
                    break
                if await request.is_disconnected() or is_aborted(session_id, request_id):
                    logger.info("Client disconnected or aborted while waiting for GraphRAG query: session=%s, req=%s", session_id, request_id)
                    yield f"data: {json.dumps({'error': {'code': 'CANCELLED', 'message': 'Request cancelled by user'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                yield ": keepalive\n\n"

            result = rag_task.result()
            elapsed = round(time.perf_counter() - t_start, 3)
            record_query_metric(elapsed, success=True)

            # Emit intermediate LangGraph pipeline stage progression
            for stage_item in result.get("pipeline_stages", []):
                yield f"event: stage\ndata: {json.dumps(stage_item)}\n\n"

            raw_ans = result.get("grounded_answer") or result.get("answer", "")
            answer = sanitize_rag_text(str(raw_ans))
            sources = []
            citations = result.get("citations", []) or []
            for c in citations:
                fn = c.get("pdf_filename") or (
                    c.get("metadata", {}).get("pdf_filename") if isinstance(c, dict) else None
                )
                if fn and fn not in sources:
                    sources.append(fn)
            if not sources and result.get("source_documents"):
                sources = result.get("source_documents")

            # Stream tokens with abort checks
            words = re.findall(r"\S+|\s+", answer)
            chunk_size = 6
            for i in range(0, len(words), chunk_size):
                if await request.is_disconnected() or is_aborted(session_id, request_id):
                    logger.info("Client disconnected or aborted: session=%s, req=%s", session_id, request_id)
                    yield f"data: {json.dumps({'error': {'code': 'CANCELLED', 'message': 'Request cancelled by user'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                token_chunk = "".join(words[i:i + chunk_size])
                yield f"event: token\ndata: {json.dumps({'token': token_chunk})}\n\n"
                await asyncio.sleep(0.002)

            suggestions = result.get("suggestions") or result.get("follow_up_inquiries", []) or []
            # Final metadata event
            final_meta = {
                "status": "SUCCESS",
                "query": message,
                "answer": answer,
                "thread_id": session_id,
                "session_id": session_id,
                "citations": citations,
                "suggestions": suggestions,
                "reply": answer,
                "grounded_answer": answer,
                "sources": sources,
                "follow_up_inquiries": suggestions,
                "verified_claims": result.get("verified_claims", []) or [],
                "top_chunks": result.get("top_chunks", []) or [],
                "subgraph": result.get("subgraph", {"nodes": [], "edges": []}) or {"nodes": [], "edges": []},
                "quality_gate_decision": _normalize_quality_gate_decision(result.get("quality_gate_decision", "accept")),
                "traceability_score": result.get("traceability_score", 0.95),
                "execution_time": elapsed,
                "latency_sec": elapsed,
                "mode_used": mode,
                "persisted": bool(session_id is not None),
                "saved": bool(session_id is not None),
                "persistence_status": "saved" if session_id else "ephemeral",
                "persistence_error": None,
            }

            # Cache & Persist consolidated response
            if redis_cache:
                redis_cache.semantic_set(
                    query=message,
                    mode=mode,
                    result=final_meta,
                    embedding=query_embedding,
                    library=library,
                    active_docs=req.active_docs,
                    ttl=86400,
                )
            if session_id and postgres_manager:
                postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                postgres_manager.save_message(session_id, "assistant", answer, mode=mode, sources=sources)

            # Emit clean completion payload adhering to standardized contract
            yield f"data: {json.dumps({'status': 'SUCCESS', 'query': message, 'answer': answer, 'thread_id': session_id, 'session_id': session_id, 'citations': citations, 'suggestions': suggestions, 'sources': sources, 'follow_up_inquiries': suggestions, 'subgraph': final_meta['subgraph'], 'verified_claims': final_meta['verified_claims'], 'top_chunks': final_meta['top_chunks'], 'quality_gate_decision': final_meta['quality_gate_decision'], 'traceability_score': final_meta['traceability_score'], 'execution_time': elapsed})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            record_query_metric(round(time.perf_counter() - t_start, 3), success=False)
            if hasattr(exc, "detail") and isinstance(exc.detail, dict):
                err_payload = {"error": exc.detail}
            elif "NO_LLM_CONFIGURED" in str(exc) or "No functional LLM provider" in str(exc):
                err_payload = {"error": {"code": "NO_LLM_CONFIGURED", "message": str(exc)}}
            else:
                err_payload = {"error": {"code": "PIPELINE_ERROR", "message": str(exc)}}
            yield f"data: {json.dumps(err_payload)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        chat_sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Redis-Cache": "MISS",
            **rate_headers,
        },
    )
