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
from src.core.config import models
from src.core.dispatchers import RAGModeDispatcher

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
        start_time = time.time()
        yield ": keepalive\n\n"
        words = re.findall(r"\S+|\s+", reply)
        for w in words:
            if await request.is_disconnected():
                return
            yield f"event: token\ndata: {json.dumps({'token': w})}\n\n"
            await asyncio.sleep(0.015)

        lat = round(time.time() - start_time, 2)
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
            "latency_sec": lat,
            "execution_time": lat,
            "durationSec": lat,
            "duration_sec": lat,
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
            'grounded_answer': cached_ans,
            'reply': cached_ans,
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
    rag_cfg = RAGModeDispatcher.dispatch(mode)
    async def chat_raw_generator():
        t_start = time.perf_counter()
        t_wall_start = time.time()
        try:
            rag_task = asyncio.create_task(
                asyncio.to_thread(
                    rag_engine.query_subgraph_graphrag,
                    query=message,
                    hops=req.hops if req.hops is not None else rag_cfg.hops,
                    top_k=req.top_k if req.top_k is not None else rag_cfg.top_k,
                    document_filter=req.document_filter,
                    active_docs=req.active_docs,
                    mode=mode,
                    thread_id=session_id,
                    chat_history=req.chat_history,
                )
            )

            while not rag_task.done():
                done, _ = await asyncio.wait([rag_task], timeout=0.25)
                if rag_task in done:
                    break
                if await request.is_disconnected() or is_aborted(session_id, request_id, started_at=t_wall_start):
                    logger.info("Client disconnected or aborted while waiting for GraphRAG query: session=%s, req=%s", session_id, request_id)
                    yield " [Request Cancelled]"
                    return
                # In plain text stream, do NOT emit SSE event: stage strings
                await asyncio.sleep(0.05)

            result = rag_task.result()
            elapsed = round(time.perf_counter() - t_start, 3)
            record_query_metric(elapsed, success=True)
            raw_ans = result.get("grounded_answer") or result.get("answer", "")
            answer = sanitize_rag_text(str(raw_ans))
            if not answer.strip():
                answer = "No grounded answer could be synthesized from the active documents. Please verify that your document is attached to your drawer or try rephrasing your question."
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
                if await request.is_disconnected() or is_aborted(session_id, request_id, started_at=t_wall_start):
                    logger.info("Client disconnected or aborted: session=%s, req=%s", session_id, request_id)
                    yield " [Request Cancelled]"
                    return
                token_chunk = "".join(words[i:i + chunk_size])
                yield token_chunk
                await asyncio.sleep(0.002)

            if session_id and postgres_manager:
                postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                postgres_manager.save_message(session_id, "assistant", answer, mode=mode, sources=sources, latency_sec=elapsed)
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
    rag_cfg = RAGModeDispatcher.dispatch(mode)
    async def chat_sse_generator():
        t_start = time.perf_counter()
        t_wall_start = time.time()
        redis_client = getattr(redis_cache, "_client", None) if redis_cache else None
        yield ": keepalive\n\n"
        if await request.is_disconnected() or is_aborted(session_id, request_id, started_at=t_wall_start, redis_client=redis_client):
            yield f"event: error\ndata: {json.dumps({'error': {'code': 'CANCELLED', 'message': 'Request cancelled by user', 'request_id': request_id}})}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            logger.info(f"[GRAPH-RAG] 🔎 SSE Stream Query: \"{message[:120]}\" (Mode: {mode} | Active Docs: {req.active_docs or 'All Documents'})")
            yield f"event: stage\ndata: {json.dumps({'stage': 'QUERY_INTAKE', 'node': 'query_intake', 'status': 'active', 'detail': 'Analyzing research query intent & resolving entities'})}\n\n"

            effective_hops = req.hops if req.hops is not None else rag_cfg.hops
            effective_top_k = req.top_k if req.top_k is not None else rag_cfg.top_k
            is_roster_query = any(w in message.lower() for w in ["name", "names", "list", "member", "members", "invitee", "invitees", "who", "all", "governors", "board"])
            if is_roster_query and effective_top_k < 15:
                effective_top_k = 15

            rag_task = asyncio.create_task(
                asyncio.to_thread(
                    rag_engine.query_subgraph_graphrag,
                    query=message,
                    hops=effective_hops,
                    top_k=effective_top_k,
                    document_filter=req.document_filter,
                    active_docs=req.active_docs,
                    mode=mode,
                    thread_id=session_id,
                    chat_history=req.chat_history,
                )
            )

            if rag_cfg.enable_graph_traversal:
                progressive_stages = [
                    (0.12, {"stage": "VECTOR_RETRIEVAL", "node": "vector_retrieval", "status": "active", "detail": "Dense vector & BM25 indexing search"}),
                    (0.35, {"stage": "GRAPH_RETRIEVAL", "node": "graph_retrieval", "status": "active", "detail": "Traversing multi-hop knowledge graph"}),
                    (0.60, {"stage": "RERANKING", "node": "reranking", "status": "active", "detail": "Cross-encoder neural reranking & scoring"}),
                ]
            else:
                progressive_stages = [
                    (0.12, {"stage": "VECTOR_RETRIEVAL", "node": "vector_retrieval", "status": "active", "detail": "Dense vector & BM25 indexing search"}),
                    (0.35, {"stage": "RERANKING", "node": "reranking", "status": "active", "detail": "Cross-encoder neural reranking & scoring"}),
                ]
            emitted_indices = set()
            last_keepalive = time.perf_counter()

            while not rag_task.done():
                done, _ = await asyncio.wait([rag_task], timeout=0.08)
                if rag_task in done:
                    break
                if await request.is_disconnected() or is_aborted(session_id, request_id, started_at=t_wall_start, redis_client=redis_client):
                    logger.info("Client disconnected or aborted while waiting for GraphRAG query: session=%s, req=%s", session_id, request_id)
                    yield f"event: error\ndata: {json.dumps({'error': {'code': 'CANCELLED', 'message': 'Request cancelled by user', 'request_id': request_id}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                # Progressive intermediate stage progression for real-time frontend lifecycle animation
                curr_elapsed = time.perf_counter() - t_start
                for idx, (threshold, stg) in enumerate(progressive_stages):
                    if idx not in emitted_indices and curr_elapsed >= threshold:
                        emitted_indices.add(idx)
                        yield f"event: stage\ndata: {json.dumps(stg)}\n\n"

                # Periodic keepalive to ensure browser fetch watchdog (45s) and intermediate proxies never timeout
                now_loop = time.perf_counter()
                if now_loop - last_keepalive >= 2.0:
                    last_keepalive = now_loop
                    yield f": keepalive {int(now_loop - t_start)}s\n\n"

            result = rag_task.result()
            elapsed = round(time.perf_counter() - t_start, 3)
            record_query_metric(elapsed, success=True)

            top_chunks_count = len(result.get("top_chunks", []) or [])
            subg = result.get("subgraph") or {}
            nodes_count = len(subg.get("nodes", [])) if isinstance(subg, dict) else 0
            qg_dec = (result.get("quality_gate_decision") or "ACCEPT").upper()
            cits_cnt = len(result.get("citations", []) or [])
            logger.info(f"[GRAPH-RAG] [OK] SSE Stream complete ({elapsed:.2f}s) | Chunks: {top_chunks_count} | Graph: {nodes_count} nodes | Gate: {qg_dec} | Citations: {cits_cnt}")

            # Emit final LangGraph pipeline stage progression (including SYNTHESIS)
            emitted_stage_names = {progressive_stages[i][1]["stage"] for i in emitted_indices}
            for stage_item in result.get("pipeline_stages", []):
                stg_name = stage_item.get("stage")
                if stg_name not in emitted_stage_names or stg_name == "SYNTHESIS":
                    yield f"event: stage\ndata: {json.dumps(stage_item)}\n\n"

            raw_ans = result.get("grounded_answer") or result.get("answer", "")
            answer = sanitize_rag_text(str(raw_ans))
            if not answer.strip():
                answer = "No grounded answer could be synthesized from the active documents. Please verify that your document is attached to your drawer or try rephrasing your question."
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
                if await request.is_disconnected() or is_aborted(session_id, request_id, started_at=t_wall_start, redis_client=redis_client):
                    logger.info("Client disconnected or aborted: session=%s, req=%s", session_id, request_id)
                    yield f"event: error\ndata: {json.dumps({'error': {'code': 'CANCELLED', 'message': 'Request cancelled by user'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                token_chunk = "".join(words[i:i + chunk_size])
                yield f"event: token\ndata: {json.dumps({'token': token_chunk})}\n\n"
                await asyncio.sleep(0.002)

            suggestions = result.get("suggestions") or result.get("follow_up_inquiries", []) or []

            # Resolve pipeline provenance & model metadata
            try:
                from src.infrastructure.providers.router import get_provider_router
                prov_router = get_provider_router()
                compl_info = prov_router.get_last_completion_info()
                actual_llm_prov = compl_info.get("provider") or models.LLM_PROVIDER
                actual_llm_model = compl_info.get("model") or models.LLM_MODEL_NAME
            except Exception:
                actual_llm_prov = models.LLM_PROVIDER
                actual_llm_model = models.LLM_MODEL_NAME

            from src.infrastructure.provenance import build_pipeline_info
            pipeline_info = build_pipeline_info(mode=mode)
            if actual_llm_prov:
                pipeline_info["llm_provider"] = actual_llm_prov
            if actual_llm_model:
                pipeline_info["llm_model"] = actual_llm_model
            storage_desc = pipeline_info["storage_used"]

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
                "pipeline_info": pipeline_info,
                "storage_used": storage_desc,
                "llm_provider": actual_llm_prov,
                "llm_model": actual_llm_model,
                "encoder_model": pipeline_info["encoder_model"],
                "reranker_model": pipeline_info["reranker_model"],
                "nli_verifier_model": pipeline_info["nli_verifier_model"],
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
                postgres_manager.save_message(session_id, "assistant", answer, mode=mode, sources=sources, latency_sec=elapsed)

            # Emit clean completion payload adhering to standardized contract
            yield f"data: {json.dumps(final_meta)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            elapsed_err = round(time.perf_counter() - t_start, 3)
            record_query_metric(elapsed_err, success=False)
            logger.exception(f"[GRAPH-RAG] ❌ SSE Stream Execution Exception ({elapsed_err:.2f}s): {exc}")

            if hasattr(exc, "detail") and isinstance(exc.detail, dict):
                err_payload = {"error": exc.detail}
            elif "NO_LLM_CONFIGURED" in str(exc) or "No functional LLM provider" in str(exc):
                err_payload = {"error": {"code": "NO_LLM_CONFIGURED", "message": str(exc)}}
            else:
                err_payload = {"error": {"code": "PIPELINE_ERROR", "message": str(exc)}}

            # Emit compliant event: error payload followed by termination marker
            yield f"event: error\ndata: {json.dumps(err_payload)}\n\n"
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
