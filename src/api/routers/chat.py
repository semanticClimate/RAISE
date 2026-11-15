"""
Chat & Conversational Reasoning Router
======================================
Component: `src.api.routers.chat`
Architecture Layer: API Gateway / Core Chat Interface

Overview:
---------
Main conversational and research chat router conforming to BACKEND_DEVELOPER_GUIDE.md
and system-architecture.md:
- Fast Mode & Expert Mode execution with LangGraph multi-engine traversal
- Dual-tier conversational memory (vLLM Qwen2.5-14B-Instruct-GPTQ-Int4)
- Server-Sent Events (SSE) streaming & plain-text raw streaming
- Token Bucket rate limiting via Redis
- Semantic & Exact Match Redis query caching
- Real-time cancellation via POST /api/chat/abort
- User feedback submission and batch query execution

Modular Architecture:
---------------------
- Conversational chat and persona memory: `src.api.routers.chat_conversational`
- Raw and SSE streaming generators: `src.api.routers.chat_streaming`
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from src.core.config import models

try:
    from prompts.system_synthesis import sanitize_rag_text
except ImportError:
    from RAG.prompts.system_synthesis import sanitize_rag_text

from src.api.context import (
    _parse_drawer_active_docs,
    clear_abort,
    get_authentic_client_ip,
    get_ready_documents_list,
    is_conversational_or_memory_query,
    record_abort,
    record_query_metric,
)
from src.api.dependencies import (
    get_postgres_manager,
    get_rag_engine,
    get_redis_cache,
    get_session_memory,
    get_chat_service,
)
from src.api.schemas import (
    AbortRequest,
    BatchChatRequest,
    ChatMessageRequest,
    FeedbackRequest,
)

# Modular imports
from src.core.dispatchers import (
    RAGMode,
    RAGModeConfig,
    RAGModeDispatcher,
    StreamFormat,
    StreamFormatDispatcher,
)
from src.api.routers.chat_conversational import handle_conversational_chat
from src.api.routers.chat_streaming import (
    create_cached_sse_stream,
    create_chat_raw_stream,
    create_chat_sse_stream,
    create_empty_drawer_raw_stream,
    create_empty_drawer_sse_stream,
)


def _normalize_quality_gate_decision(val: Any) -> str:
    """
    Normalizes internal quality gate decisions to match frontend Zod schema:
    'accept' | 'retry' | 'unable_to_verify' | 'empty_workspace'
    Maps internal states ('active' -> 'accept', 'refusal' -> 'unable_to_verify').
    """
    s = str(val or "accept").lower().strip()
    if s in ("accept", "active", "pass", "passed", "success"):
        return "accept"
    if s == "retry":
        return "retry"
    if s in ("empty_workspace", "empty_drawer", "no_docs"):
        return "empty_workspace"
    return "unable_to_verify"


logger = logging.getLogger("raise.router.chat")
router = APIRouter(tags=["Chat & Reasoning"])


@router.post("/api/chat")
@router.post("/api/chat/stream")
@router.post("/chat")
@router.post("/chat/stream")
async def chat_endpoint(
    req: ChatMessageRequest,
    request: Request,
    rag_engine: Any = Depends(get_rag_engine),
    postgres_manager: Any = Depends(get_postgres_manager),
    redis_cache: Any = Depends(get_redis_cache),
    session_memory_manager: Any = Depends(get_session_memory),
    chat_service: Any = Depends(get_chat_service),
):
    """
    Main Chat Endpoint conforming to BACKEND_DEVELOPER_GUIDE.md and system-architecture.md:
    - Supports Fast Mode (speed-first) and Expert Mode (depth-first).
    - Supports Server-Sent Events (SSE) streaming when stream=True or via /api/chat/stream.
    - Token Bucket rate limiting via Redis with X-RateLimit-Remaining header.
    - Caches repeated queries in Redis with X-Redis-Cache header.
    - Persists session turns in PostgreSQL.
    - Supports real-time cancellation via POST /api/chat/abort.
    """
    if request.url.path.endswith("/stream"):
        req.stream = True
    raw_query = req.query or req.message or ""
    message = raw_query.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Modular switch-case dispatch for RAG mode configuration
    rag_mode_config = RAGModeDispatcher.dispatch(req.mode)
    mode = rag_mode_config.mode.value
    effective_hops = req.hops if req.hops is not None else rag_mode_config.hops
    effective_top_k = req.top_k if req.top_k is not None else rag_mode_config.top_k

    # Dynamic retrieval depth expansion for roster, membership, and enumeration queries
    is_roster_query = any(w in message.lower() for w in ["name", "names", "list", "member", "members", "invitee", "invitees", "who", "all", "governors", "board"])
    if is_roster_query and effective_top_k < 15:
        effective_top_k = 15

    # Modular switch-case content negotiation for stream format
    stream_format = StreamFormatDispatcher.resolve_from_request(
        format_param=req.format,
        accept_header=request.headers.get("accept", ""),
        stream_requested=bool(req.stream),
    )
    session_id = req.session_id or req.thread_id or "default"
    request_id = req.request_id or f"req-{int(time.time() * 1000)}"
    library = req.library

    # 0. Purge any stale cancellation tokens for this session / request so new query executes cleanly
    clear_abort(session_id=session_id, request_id=request_id, redis_mgr=redis_cache)

    # Normalize, unquote, and handle URL encoded spaces in active_docs
    if req.active_docs is not None:
        req.active_docs = _parse_drawer_active_docs(req.active_docs)

    logger.info(f"[GRAPH-RAG] 🔎 Query: \"{message}\" (Mode: {mode} | Active Docs: {req.active_docs or 'All Documents'})")

    # 0. Rate Limiting Check (Token Bucket with Authentic Proxy IP Resolution)
    is_allowed, rate_headers = chat_service.check_rate_limit(request, request_id)
    if not is_allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "Too Many Requests", "detail": "API rate limit exceeded. Please retry momentarily."},
            headers=rate_headers,
        )

    # 0.5 Modular Slash Commands System (/compare, /audit, /browser, /help)
    if message.startswith("/"):
        from src.features.commands.chat_bridge import handle_slash_command_chat
        cmd_resp = await handle_slash_command_chat(
            req=req,
            request=request,
            message=message,
            session_id=session_id,
            request_id=request_id,
            mode=mode,
            rate_headers=rate_headers,
            rag_engine=rag_engine,
            postgres_manager=postgres_manager,
        )
        if cmd_resp is not None:
            return cmd_resp

    # 1. Conversational & Memory Routing: Introductions, chit-chat, and memory recall bypass drawer check
    if is_conversational_or_memory_query(message):
        return await handle_conversational_chat(
            req=req,
            request=request,
            message=message,
            session_id=session_id,
            mode=mode,
            rate_headers=rate_headers,
            postgres_manager=postgres_manager,
            redis_cache=redis_cache,
            session_memory_manager=session_memory_manager,
        )

    # 2. Document Research Queries: Validate active_docs and Enforce Drawer Guard
    ready_docs = get_ready_documents_list()
    pg_docs = postgres_manager.list_documents() if postgres_manager else []
    vector_docs = rag_engine.vector_engine.get_active_workspace_documents() if rag_engine and hasattr(rag_engine, "vector_engine") and rag_engine.vector_engine else []
    is_empty_workspace = (len(ready_docs) == 0 and len(pg_docs) == 0 and len(vector_docs) == 0)

    # If session_id provided and req.active_docs specified, cross-reference with session drawer
    session_drawer = None
    if session_id and postgres_manager:
        session_drawer = postgres_manager.get_session_drawer(session_id)
        if session_drawer and ready_docs:
            resolved_drawer: List[str] = []
            for d in session_drawer:
                if isinstance(d, str) and d.endswith(".pdf"):
                    resolved_drawer.append(d)
                else:
                    matched_fn = None
                    for rd in ready_docs:
                        fn = rd.get("filename") if isinstance(rd, dict) else None
                        if fn and (d == rd.get("id") or (isinstance(d, str) and d in fn)):
                            matched_fn = fn
                            break
                    if not matched_fn and len(ready_docs) == 1 and ready_docs[0].get("filename"):
                        matched_fn = ready_docs[0]["filename"]
                    resolved_drawer.append(matched_fn or d)
            session_drawer = resolved_drawer

        if session_drawer and req.active_docs:
            for doc in req.active_docs:
                doc_clean = doc.replace("src-doc_", "").rsplit(".", 1)[0].lower()
                matches = any(
                    doc == d or doc in d or d in doc or
                    doc_clean == d.replace("src-doc_", "").rsplit(".", 1)[0].lower()
                    for d in session_drawer
                )
                if not matches:
                    logger.warning("Session %s: Document '%s' in active_docs is not in session drawer %s", session_id, doc, session_drawer)

    # If active_docs contains temporary upload IDs (e.g. "src-..."), resolve them to ready document filenames
    if req.active_docs:
        resolved_docs: List[str] = []
        for doc in req.active_docs:
            if doc.endswith(".pdf"):
                resolved_docs.append(doc)
            else:
                matched = False
                for rd in ready_docs:
                    fn = rd.get("filename") if isinstance(rd, dict) else None
                    if fn and (doc == rd.get("id") or doc in fn):
                        resolved_docs.append(fn)
                        matched = True
                        break
                if not matched and len(ready_docs) == 1 and ready_docs[0].get("filename"):
                    resolved_docs.append(ready_docs[0]["filename"])
        if resolved_docs:
            req.active_docs = resolved_docs

    has_empty_drawer = (req.active_docs is not None and len(req.active_docs) == 0) or (req.active_docs is None and session_drawer is not None and len(session_drawer) == 0)

    # For default / CLI / terminal sessions without an explicit drawer, auto-bind ready documents if available
    if (session_id == "default" or session_drawer is None) and req.active_docs is None and len(ready_docs) > 0:
        req.active_docs = [d.get("filename") for d in ready_docs if isinstance(d, dict) and d.get("filename")]
        has_empty_drawer = False

    if has_empty_drawer or is_empty_workspace:
        if has_empty_drawer:
            immediate_reply = "No active documents are currently attached to your drawer. Please attach a document in the drawer to begin research."
        else:
            immediate_reply = "No documents have been uploaded to the workspace yet. Please upload an academic PDF or report to RAISE to begin research and analysis."

        if session_id:
            if postgres_manager:
                postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                postgres_manager.save_message(session_id, "assistant", immediate_reply, mode=mode, sources=[])
            if redis_cache:
                redis_cache.save_session_message(session_id, "user", message, mode=mode)
                redis_cache.save_session_message(session_id, "assistant", immediate_reply, mode=mode)

        # Modular switch-case dispatch for empty drawer streaming response
        match stream_format:
            case StreamFormat.RAW:
                return create_empty_drawer_raw_stream(immediate_reply, request, rate_headers)
            case StreamFormat.SSE:
                return create_empty_drawer_sse_stream(immediate_reply, request, mode, session_id, rate_headers)
            case _:
                pass

        # If non-streaming
        return JSONResponse(
            content={
                "status": "SUCCESS",
                "reply": immediate_reply,
                "grounded_answer": immediate_reply,
                "answer": immediate_reply,
                "sources": [],
                "citations": [],
                "verified_claims": [],
                "subgraph": {"nodes": [], "edges": []},
                "quality_gate_decision": "accept",
                "traceability_score": 0.95,
                "execution_time": 0.005,
                "latency_sec": 0.005,
                "durationSec": 0.005,
                "mode_used": mode,
                "thread_id": session_id,
                "session_id": session_id,
            },
            headers={"X-Process-Time-Ms": "5.0", **rate_headers},
        )

    # 1. Check Redis Semantic & Exact Match Cache
    query_embedding = None
    try:
        if rag_engine and hasattr(rag_engine, "vector_engine") and rag_engine.vector_engine:
            emb_res = await asyncio.to_thread(rag_engine.vector_engine.compute_embeddings, [message])
            if emb_res and len(emb_res) > 0:
                query_embedding = emb_res[0]
    except Exception:
        query_embedding = None

    cached = None
    if redis_cache:
        cached = redis_cache.semantic_get(
            query=message,
            mode=mode,
            embedding=query_embedding,
            threshold=0.95,
            library=library,
            active_docs=req.active_docs,
        )

    if not req.stream and cached:
        cached_ans = cached.get("answer") or cached.get("reply") or cached.get("grounded_answer") or ""
        suggestions = cached.get("suggestions") or cached.get("follow_up_inquiries", [])
        payload = {
            "status": "SUCCESS",
            "query": message,
            "answer": cached_ans,
            "thread_id": session_id,
            "session_id": session_id,
            "citations": cached.get("citations", []),
            "suggestions": suggestions,
            "reply": cached_ans,
            "grounded_answer": cached_ans,
            "sources": cached.get("sources", []),
            "follow_up_inquiries": cached.get("follow_up_inquiries", suggestions),
            "verified_claims": cached.get("verified_claims", []),
            "subgraph": cached.get("subgraph", {"nodes": [], "edges": []}),
            "top_chunks": cached.get("top_chunks", []),
            "quality_gate_decision": _normalize_quality_gate_decision(cached.get("quality_gate_decision", "accept")),
            "selected_tools": cached.get("selected_tools", ["redis_cache"]),
            "decomposed_queries": cached.get("decomposed_queries", []),
            "traceability_score": cached.get("traceability_score", 0.98),
            "execution_time": 0.005,
            "latency_sec": 0.005,
            "durationSec": 0.005,
            "mode_used": mode,
        }
        if session_id and postgres_manager:
            postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
            postgres_manager.save_message(session_id, "assistant", cached_ans, mode=mode, sources=payload["sources"])
        record_query_metric(0.005, success=True)
        return JSONResponse(
            content=payload,
            headers={"X-Redis-Cache": "HIT", "X-Process-Time-Ms": "5.0", **rate_headers},
        )

    if req.stream and cached:
        return create_cached_sse_stream(cached, request, session_id, request_id, rate_headers)

    # 2. Non-Streaming Execution
    if not req.stream:
        try:
            result, elapsed = await asyncio.to_thread(
                chat_service.execute_rag_query,
                message=message,
                mode=mode,
                session_id=session_id,
                active_docs=req.active_docs,
                document_filter=req.document_filter,
                hops=effective_hops,
                top_k=effective_top_k,
                chat_history=req.chat_history,
            )
        except HTTPException:
            record_query_metric(0.0, success=False)
            raise
        except Exception as exc:
            record_query_metric(0.0, success=False)
            raise HTTPException(status_code=500, detail=f"Pipeline error: {str(exc)}")

        raw_ans = result.get("grounded_answer") or result.get("answer", "")
        answer = sanitize_rag_text(str(raw_ans))
        if not answer.strip():
            answer = "No grounded answer could be synthesized from the active documents. Please verify your document selection in the drawer."
        sources = []
        for c in result.get("citations", []):
            fn = c.get("pdf_filename") or (c.get("metadata", {}).get("pdf_filename") if isinstance(c, dict) else None)
            if fn and fn not in sources:
                sources.append(fn)
        if not sources and result.get("source_documents"):
            sources = result.get("source_documents")

        suggestions = result.get("suggestions") or result.get("follow_up_inquiries", []) or []
        citations = result.get("citations", []) or []

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

        response_payload = {
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
            "subgraph": result.get("subgraph", {"nodes": [], "edges": []}) or {"nodes": [], "edges": []},
            "top_chunks": result.get("top_chunks", []) or [],
            "quality_gate_decision": _normalize_quality_gate_decision(result.get("quality_gate_decision", "accept")),
            "selected_tools": result.get("selected_tools", []) or [],
            "decomposed_queries": result.get("decomposed_queries", []) or [],
            "traceability_score": result.get("traceability_score", 0.95),
            "execution_time": elapsed,
            "latency_sec": elapsed,
            "durationSec": elapsed,
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

        top_chunks_count = len(response_payload.get("top_chunks", []))
        subg = response_payload.get("subgraph") or {}
        nodes_count = len(subg.get("nodes", [])) if isinstance(subg, dict) else 0
        qg_dec = response_payload.get("quality_gate_decision", "accept").upper()
        logger.info(f"[GRAPH-RAG] ✅ Answer synthesized in {elapsed:.2f}s | Chunks: {top_chunks_count} | Graph: {nodes_count} nodes | Gate: {qg_dec} | Citations: {len(citations)}")

        # Cache in Redis with semantic vector indexing (TTL: 86400s / 24h)
        if redis_cache:
            redis_cache.semantic_set(
                query=message,
                mode=mode,
                result=response_payload,
                embedding=query_embedding,
                library=library,
                active_docs=req.active_docs,
                ttl=86400,
            )

        # Persist in PostgreSQL
        if session_id and postgres_manager:
            postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
            postgres_manager.save_message(session_id, "assistant", answer, mode=mode, sources=sources, latency_sec=elapsed)

        return JSONResponse(
            content=response_payload,
            headers={
                "X-Redis-Cache": "MISS",
                "X-Process-Time-Ms": str(round(elapsed * 1000, 1)),
                **rate_headers,
            },
        )

    # 3. Modular Streaming Execution via StreamFormatDispatcher
    if stream_format == StreamFormat.RAW:
        return create_chat_raw_stream(
            rag_engine=rag_engine,
            message=message,
            req=req,
            mode=mode,
            session_id=session_id,
            request_id=request_id,
            request=request,
            postgres_manager=postgres_manager,
            rate_headers=rate_headers,
        )

    # SSE Streaming Execution with Real-Time Cancellation & Progressive Stage Events
    return create_chat_sse_stream(
        rag_engine=rag_engine,
        message=message,
        req=req,
        mode=mode,
        session_id=session_id,
        request_id=request_id,
        library=library,
        query_embedding=query_embedding,
        request=request,
        postgres_manager=postgres_manager,
        redis_cache=redis_cache,
        rate_headers=rate_headers,
    )


@router.post("/api/chat/abort")
async def abort_chat_generation(req: AbortRequest):
    """
    Tier 1 Critical: Cancel in-flight streaming or execution for a session or request ID.
    """
    sid = req.session_id or req.thread_id
    rid = req.request_id
    if not sid and not rid:
        raise HTTPException(status_code=400, detail="session_id or request_id required")
    record_abort(sid, rid)
    return {
        "status": "aborted",
        "session_id": sid,
        "request_id": rid,
        "message": "Chat generation cancelled successfully",
    }


@router.post("/api/feedback")
async def submit_chat_feedback(
    fb: FeedbackRequest,
    request: Request,
    postgres_manager: Any = Depends(get_postgres_manager),
):
    """
    Tier 2 High Value: Record user feedback on response relevance and accuracy into PostgreSQL.
    """
    sid = fb.session_id or "default"
    ip = get_authentic_client_ip(request)
    if postgres_manager:
        postgres_manager.save_feedback(
            session_id=sid,
            rating=fb.rating,
            reason=fb.reason,
            query=fb.query,
            message_id=fb.message_id,
            client_ip=ip,
        )
    return {
        "status": "recorded",
        "session_id": sid,
        "rating": fb.rating,
        "message": "Feedback recorded successfully",
    }


@router.get("/api/feedback/stats")
async def get_feedback_stats_endpoint(
    postgres_manager: Any = Depends(get_postgres_manager),
):
    """
    Operational Telemetry: Overall thumbs_up vs thumbs_down counts and satisfaction ratio.
    """
    if not postgres_manager:
        return {
            "thumbs_up": 0,
            "thumbs_down": 0,
            "satisfaction_ratio": 1.0,
            "total_feedback": 0,
        }
    try:
        return postgres_manager.get_feedback_stats()
    except Exception as exc:
        logger.error("Error fetching feedback stats: %s", exc)
        raise HTTPException(status_code=503, detail="Database feedback analytics unavailable")


@router.post("/api/chat/batch")
async def batch_chat_query(
    req: BatchChatRequest,
    rag_engine: Any = Depends(get_rag_engine),
):
    """
    Tier 3 Medium: Execute research query across multiple document filters in parallel.
    """
    filters = req.doc_filters or req.documents or []
    if not filters:
        ready_docs = get_ready_documents_list()
        filters = [d["filename"] for d in ready_docs]

    results = []
    for doc in filters[:5]:
        res = rag_engine.query_subgraph_graphrag(
            query=req.query,
            mode=req.mode or "fast",
            document_filter=doc,
            active_docs=[doc],
        )
        ans = res.get("grounded_answer") or res.get("answer", "")
        results.append({
            "document": doc,
            "answer": ans,
            "reply": ans,
            "grounded_answer": ans,
            "citations": res.get("citations", []),
            "quality_gate_decision": _normalize_quality_gate_decision(res.get("quality_gate_decision", "accept")),
            "grounded": res.get("grounded", True),
        })

    return {"query": req.query, "mode": req.mode or "fast", "results": results, "count": len(results)}
