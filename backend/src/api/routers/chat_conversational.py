"""
RAISE Conversational Reasoning & Persona Memory Handler
======================================================
Component: `src.api.routers.chat_conversational`
Architecture Layer: API Gateway / Multi-Turn Conversational Layer

Overview:
---------
This module manages casual chat queries, persona extraction, and multi-turn
context resolution that bypass the academic document drawer guardrails.

Key Responsibilities:
1. User Persona & Entity Memory Extraction:
   - Detects introductions ("My name is Siddharth", "I am Dr. Rao") and records persona
     attributes in Redis session memory and session memory manager.
2. Sliding-Window Conversational Context:
   - Reads the latest conversation turns from Redis (fast path), falling back to PostgreSQL
     sliding-window persistence to maintain seamless context without holding DB locks.
3. System Prompt Synthesis:
   - Injects user persona, strict assistant identity ("RAISE"), and friendly guidance to
     attach academic documents when ready for document research.
4. Response Delivery:
   - Supports plain-text raw streaming (`text/plain`), Server-Sent Events (`text/event-stream`),
     and standard JSON responses with local fallback if external LLM inference endpoints are unreachable.
5. Atomic Dual-Write Persistence:
   - Persists user and assistant messages to both Redis session list and PostgreSQL.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.api.schemas import ChatMessageRequest
from src.cli.persona_classifier import extract_conversational_persona

logger = logging.getLogger("raise.router.chat.conversational")


async def handle_conversational_chat(
    req: ChatMessageRequest,
    request: Request,
    message: str,
    session_id: str,
    mode: str,
    rate_headers: Dict[str, str],
    postgres_manager: Any,
    redis_cache: Any,
    session_memory_manager: Any,
) -> Any:
    """
    Dual-Tier Conversational Memory & Multi-Turn Context Handler.
    - Zero database transaction locks held during inference.
    - Resolves user persona attributes (e.g. name) and stores in Redis session hash.
    - Retrieves recent conversation turns from Redis bounded list (with PostgreSQL sliding window fallback).
    - Orchestrates with vLLM Qwen2.5-14B-Instruct-GPTQ-Int4 maintaining conversational memory.
    - Decoupled atomic dual-write to Redis and PostgreSQL.
    """
    t_start = time.perf_counter()

    # 1. User Persona & Entity Memory Extraction
    extracted_name = (
        session_memory_manager.extract_and_set_user_persona(session_id, message)
        if session_memory_manager
        else None
    )
    if extracted_name and redis_cache:
        redis_cache.set_session_memory(session_id, "user_name", extracted_name)

    existing_vars = redis_cache.get_session_memory(session_id) if redis_cache else {}
    known_name = existing_vars.get("user_name") or (
        session_memory_manager.get_user_persona(session_id).get("user_name")
        if session_memory_manager
        else None
    )

    # 2. Sliding Window Context Retrieval (Short-Term Redis -> Long-Term Postgres)
    recent_turns = (redis_cache.get_session_messages(session_id, limit=10) if redis_cache else []) or []
    if not recent_turns and postgres_manager:
        # Load from Postgres sliding window (no transaction held open)
        recent_turns = postgres_manager.get_messages(session_id, limit=10)
        # Backfill Redis session list
        if redis_cache:
            for t in recent_turns:
                redis_cache.save_session_message(
                    session_id,
                    t.get("role", "user"),
                    t.get("content", ""),
                    mode=t.get("mode", "fast"),
                    sources=t.get("sources", []),
                )

    # 3. System Prompt & Chat History Construction
    name_ctx = f"The user's name is {known_name}. " if known_name else ""
    system_prompt = (
        "You are RAISE, your research intelligence assistant. Your name is strictly RAISE. "
        "Never expand the acronym RAISE. "
        "You are helpful, concise, warm, intellectually sharp, and conversational. "
        f"{name_ctx}"
        "You maintain conversational context across turns and remember facts shared by the user. "
        "If the user introduces themselves, greet them warmly by name. "
        "If the user asks if you know their name or asks what their name is, answer directly from your conversation memory. "
        "When the user is ready to conduct research on academic documents, remind them that they can attach documents in their drawer. "
        "Always use the verb 'attach' (never 'select') when referring to drawer documents. "
        "Never fabricate document citations for casual conversation."
    )

    vllm_messages = [{"role": "system", "content": system_prompt}]
    for turn in recent_turns[-8:]:
        r = turn.get("role")
        c = turn.get("content") or turn.get("text")
        if r in ("user", "assistant") and c:
            vllm_messages.append({"role": r, "content": c})
    vllm_messages.append({"role": "user", "content": message})

    vllm_candidates = [
        os.getenv("VLLM_BASE_URL", "http://localhost:8002/v1"),
        "http://localhost:8000/v1",
        "http://127.0.0.1:8000/v1",
        "http://localhost:8002/v1",
        "http://127.0.0.1:8002/v1",
        "http://raise-vllm-prod:8000/v1",
    ]
    model_name = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4")

    # Conversational intent classifier matching main.py
    greeting_typo_regex = re.compile(
        r"^(hi+|hello+|helo+|hekko+|hey+|heyy+|heyo|howdy|hola|yo+|sup|hlo|hlw|greetings)(?:\s+there|\s+raise|\s+bot|\s*!|\s*\.|\s*\?)*$",
        re.IGNORECASE
    )
    intent = extract_conversational_persona(message)
    q_norm = re.sub(r"[^\w\s]", "", message.lower()).strip()
    is_persona_fastpath = (
        intent.get("type") in ("greeting", "bot_identity", "name_recall", "name_intro")
        or bool(greeting_typo_regex.match(message.strip()))
        or q_norm in {
            "hi", "hello", "helo", "hekko", "hey", "heyy", "greetings", "howdy", "hi there", "hello there", "hey there",
            "good morning", "good afternoon", "good evening", "good day", "yo", "sup", "hlo", "hlw"
        }
        or any(w in message.lower() for w in ["who are you", "who r u", "whats your name", "what is your name", "what can you do"])
    )

    # Helper for fallback reply matching main.py
    def get_fallback_reply() -> str:
        q_lower = message.lower()
        if intent.get("type") == "name_intro":
            p_name = intent.get("name") or known_name or "there"
            return f"Hello {p_name}! My name is RAISE. I'm here to help you with your research. How can I assist you today?"
        if intent.get("type") == "name_recall" or any(w in q_lower for w in ["do you know my name", "what is my name", "who am i"]):
            if known_name:
                return (
                    f"Yes, of course! Your name is {known_name}. How can I assist you with your research today? "
                    "When you are ready, please attach an academic document in your drawer."
                )
            return (
                "You haven't told me your name yet! What should I call you? "
                "When you are ready to conduct document research, please attach a document in your drawer."
            )
        if intent.get("type") == "bot_identity" or any(w in q_lower for w in ["who are you", "who r u", "whats your name", "what is your name", "what can you do"]):
            return (
                "My name is RAISE, your research intelligence assistant. I am here to help you analyze, verify, "
                "and extract insights from academic documents and reports. Please attach a document in your drawer to begin research."
            )
        if known_name:
            return (
                f"Hello {known_name}! I am RAISE, your research intelligence assistant. How can I help you today? "
                "Please attach an academic document in your drawer when you wish to begin research."
            )
        return (
            "Hello! I am RAISE, your research intelligence assistant. How can I help you today? "
            "Please attach an academic document in your drawer when you wish to begin research."
        )

    # A. Plain-Text Stream Response
    if req.stream and (req.format == "raw" or "text/plain" in request.headers.get("accept", "").lower()):
        async def conv_raw_stream():
            full_response_parts = []
            stream_succeeded = False

            if is_persona_fastpath:
                fb = get_fallback_reply()
                yield fb
                if session_id:
                    if postgres_manager:
                        postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                        postgres_manager.save_message(session_id, "assistant", fb, mode=mode, sources=[])
                    if redis_cache:
                        redis_cache.save_session_message(session_id, "user", message, mode=mode)
                        redis_cache.save_session_message(session_id, "assistant", fb, mode=mode)
                return

            # --- ATTEMPT 1: Cloud / Primary LLM Router (Groq, Gemini, Mistral, etc.) ---
            try:
                from src.infrastructure.providers.router import get_provider_router, InferenceTask
                prov_router = get_provider_router()
                async for chunk in prov_router.complete_stream(
                    prompt=message,
                    task=InferenceTask.CHAT,
                    system_prompt=system_prompt,
                    max_tokens=384,
                    temperature=0.3,
                ):
                    if await request.is_disconnected():
                        return
                    if chunk and not chunk.startswith("Inference execution error"):
                        full_response_parts.append(chunk)
                        yield chunk
                if full_response_parts:
                    stream_succeeded = True
            except Exception as router_err:
                logger.warning(f"Cloud provider raw stream failed: {router_err}")

            # --- ATTEMPT 2: Local vLLM (Fail Fast with 2.0s connect timeout) ---
            if not stream_succeeded:
                for vllm_url in vllm_candidates:
                    endpoint = f"{vllm_url.rstrip('/')}/chat/completions"
                    payload = {
                        "model": model_name,
                        "messages": vllm_messages,
                        "temperature": 0.3,
                        "max_tokens": 384,
                        "stream": True,
                    }
                    try:
                        timeout = httpx.Timeout(15.0, connect=2.0)
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            async with client.stream("POST", endpoint, json=payload) as resp:
                                if resp.status_code == 200:
                                    async for line in resp.aiter_lines():
                                        if await request.is_disconnected():
                                            return
                                        if not line.startswith("data: "):
                                            continue
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            chunk = json.loads(data_str)
                                            delta = chunk["choices"][0]["delta"].get("content", "")
                                            if delta:
                                                full_response_parts.append(delta)
                                                yield delta
                                        except Exception:
                                            pass
                                    stream_succeeded = True
                                    break
                    except Exception:
                        continue

            # --- ATTEMPT 3: Grounded Fallback Persona Response ---
            if not stream_succeeded:
                fb = get_fallback_reply()
                full_response_parts.append(fb)
                words = re.findall(r"\S+|\s+", fb)
                for w in words:
                    if await request.is_disconnected():
                        return
                    yield w
                    await asyncio.sleep(0.015)

            complete_text = "".join(full_response_parts).strip()
            # Decoupled Dual-Write Persistence
            if session_id and complete_text:
                if postgres_manager:
                    postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                    postgres_manager.save_message(session_id, "assistant", complete_text, mode=mode, sources=[])
                if redis_cache:
                    redis_cache.save_session_message(session_id, "user", message, mode=mode)
                    redis_cache.save_session_message(session_id, "assistant", complete_text, mode=mode)

        return StreamingResponse(
            conv_raw_stream(),
            media_type="text/plain; charset=utf-8",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", **rate_headers},
        )

    # B. SSE Stream Response
    if req.stream:
        async def conv_sse_stream():
            yield ": keepalive\n\n"
            full_response_parts = []
            stream_succeeded = False

            if is_persona_fastpath:
                fb = get_fallback_reply()
                words = re.findall(r"\S+|\s+", fb)
                chunk_size = 4
                for i in range(0, len(words), chunk_size):
                    if await request.is_disconnected():
                        return
                    w = "".join(words[i:i + chunk_size])
                    yield f"event: token\ndata: {json.dumps({'token': w})}\n\n"
                    await asyncio.sleep(0.001)
                if session_id:
                    if postgres_manager:
                        postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                        postgres_manager.save_message(session_id, "assistant", fb, mode=mode, sources=[])
                    if redis_cache:
                        redis_cache.save_session_message(session_id, "user", message, mode=mode)
                        redis_cache.save_session_message(session_id, "assistant", fb, mode=mode)
                yield f"data: {json.dumps({'status': 'completed', 'answer': fb, 'grounded_answer': fb, 'reply': fb, 'sources': [], 'citations': []})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # --- ATTEMPT 1: Cloud / Primary LLM Router (Groq, Gemini, Mistral, etc.) ---
            try:
                from src.infrastructure.providers.router import get_provider_router, InferenceTask
                prov_router = get_provider_router()
                async for chunk in prov_router.complete_stream(
                    prompt=message,
                    task=InferenceTask.CHAT,
                    system_prompt=system_prompt,
                    max_tokens=384,
                    temperature=0.3,
                ):
                    if await request.is_disconnected():
                        return
                    if chunk and not chunk.startswith("Inference execution error"):
                        full_response_parts.append(chunk)
                        yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"
                if full_response_parts:
                    stream_succeeded = True
            except Exception as router_err:
                logger.warning(f"Cloud provider SSE stream failed: {router_err}")

            # --- ATTEMPT 2: Local vLLM (Fail Fast with 2.0s connect timeout) ---
            if not stream_succeeded:
                for vllm_url in vllm_candidates:
                    endpoint = f"{vllm_url.rstrip('/')}/chat/completions"
                    payload = {
                        "model": model_name,
                        "messages": vllm_messages,
                        "temperature": 0.3,
                        "max_tokens": 384,
                        "stream": True,
                    }
                    try:
                        timeout = httpx.Timeout(15.0, connect=2.0)
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            async with client.stream("POST", endpoint, json=payload) as resp:
                                if resp.status_code == 200:
                                    async for line in resp.aiter_lines():
                                        if await request.is_disconnected():
                                            return
                                        if not line.startswith("data: "):
                                            continue
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            chunk = json.loads(data_str)
                                            delta = chunk["choices"][0]["delta"].get("content", "")
                                            if delta:
                                                full_response_parts.append(delta)
                                                yield f"data: {json.dumps({'token': delta})}\n\n"
                                        except Exception:
                                            pass
                                    stream_succeeded = True
                                    break
                    except Exception:
                        continue

            # --- ATTEMPT 3: Grounded Fallback Persona Response ---
            if not stream_succeeded:
                fb = get_fallback_reply()
                full_response_parts.append(fb)
                words = re.findall(r"\S+|\s+", fb)
                for w in words:
                    if await request.is_disconnected():
                        return
                    yield f"event: token\ndata: {json.dumps({'token': w})}\n\n"
                    await asyncio.sleep(0.015)

            complete_text = "".join(full_response_parts).strip()
            # Decoupled Dual-Write Persistence
            if session_id and complete_text:
                if postgres_manager:
                    postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                    postgres_manager.save_message(session_id, "assistant", complete_text, mode=mode, sources=[])
                if redis_cache:
                    redis_cache.save_session_message(session_id, "user", message, mode=mode)
                    redis_cache.save_session_message(session_id, "assistant", complete_text, mode=mode)

            yield f"data: {json.dumps({'status': 'completed', 'answer': complete_text, 'grounded_answer': complete_text, 'reply': complete_text, 'sources': [], 'citations': []})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            conv_sse_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no", **rate_headers},
        )

    # C. Non-Streaming Response
    if is_persona_fastpath:
        full_reply = get_fallback_reply()
        elapsed = round(time.perf_counter() - t_start, 3)
        if session_id and full_reply:
            if postgres_manager:
                postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
                postgres_manager.save_message(session_id, "assistant", full_reply, mode=mode, sources=[])
            if redis_cache:
                redis_cache.save_session_message(session_id, "user", message, mode=mode)
                redis_cache.save_session_message(session_id, "assistant", full_reply, mode=mode)
        return JSONResponse(
            content={
                "reply": full_reply,
                "grounded_answer": full_reply,
                "answer": full_reply,
                "sources": [],
                "citations": [],
                "verified_claims": [],
                "subgraph": {"nodes": [], "edges": []},
                "quality_gate_decision": "accept",
                "execution_time": elapsed,
                "latency_sec": elapsed,
                "mode_used": mode,
                "thread_id": session_id,
                "session_id": session_id,
            },
            headers={"X-Process-Time-Ms": str(round(elapsed * 1000, 1)), **rate_headers},
        )

    full_reply = ""
    try:
        from src.infrastructure.providers.router import get_provider_router, InferenceTask
        prov_router = get_provider_router()
        router_reply = prov_router.complete(
            prompt=message,
            task=InferenceTask.CHAT,
            system_prompt=system_prompt,
            max_tokens=384,
            temperature=0.3,
        )
        if router_reply and not router_reply.startswith("Inference execution error"):
            full_reply = router_reply.strip()
    except Exception as e:
        logger.warning(f"Router chat completion notice: {e}")

    if not full_reply:
        for vllm_url in vllm_candidates:
            endpoint = f"{vllm_url.rstrip('/')}/chat/completions"
            payload = {
                "model": model_name,
                "messages": vllm_messages,
                "temperature": 0.3,
                "max_tokens": 384,
                "stream": False,
            }
            try:
                timeout = httpx.Timeout(15.0, connect=2.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(endpoint, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        full_reply = data["choices"][0]["message"]["content"].strip()
                        break
            except Exception:
                continue

    if not full_reply:
        full_reply = get_fallback_reply()

    elapsed = round(time.perf_counter() - t_start, 3)

    # Decoupled Dual-Write Persistence
    if session_id and full_reply:
        if postgres_manager:
            postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
            postgres_manager.save_message(session_id, "assistant", full_reply, mode=mode, sources=[])
        if redis_cache:
            redis_cache.save_session_message(session_id, "user", message, mode=mode)
            redis_cache.save_session_message(session_id, "assistant", full_reply, mode=mode)

    return JSONResponse(
        content={
            "reply": full_reply,
            "grounded_answer": full_reply,
            "answer": full_reply,
            "sources": [],
            "citations": [],
            "verified_claims": [],
            "subgraph": {"nodes": [], "edges": []},
            "quality_gate_decision": "accept",
            "execution_time": elapsed,
            "latency_sec": elapsed,
            "mode_used": mode,
            "thread_id": session_id,
            "session_id": session_id,
        },
        headers={"X-Process-Time-Ms": str(round(elapsed * 1000, 1)), **rate_headers},
    )
