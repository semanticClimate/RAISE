"""
Slash Commands Chat Bridge & Router Integration
===============================================
Component: `src.features.commands.chat_bridge`
Architecture: Bridge connecting Chat API Router with Slash Commands Engine
Max Lines: Strictly < 400 lines
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from . import execute_slash_command, is_slash_command
from .types import CommandResult

logger = logging.getLogger("raise.commands.bridge")


async def handle_slash_command_chat(
    req: Any,
    request: Request,
    message: str,
    session_id: str,
    request_id: str,
    mode: str,
    rate_headers: Dict[str, str],
    rag_engine: Any = None,
    postgres_manager: Any = None,
) -> Optional[Any]:
    """
    Executes a slash command from the chat pipeline and returns the appropriate
    HTTP or SSE streaming response.
    """
    if not is_slash_command(message):
        return None

    cmd_res = execute_slash_command(
        raw_query=message,
        active_docs=req.active_docs,
        session_id=session_id,
        request_id=request_id,
        mode=mode,
        stream=bool(getattr(req, "stream", False)),
        rag_engine=rag_engine,
    )

    if not cmd_res:
        return None

    res_dict = cmd_res.to_dict()
    res_dict["query"] = message

    # Persist command interaction in PostgreSQL session history
    if session_id and postgres_manager:
        try:
            postgres_manager.save_message(session_id, "user", message, mode=mode, active_docs=req.active_docs)
            postgres_manager.save_message(session_id, "assistant", cmd_res.answer, mode=mode, sources=[])
        except Exception as e:
            logger.debug("Could not persist command history to postgres: %s", e)

    # If SSE streaming is requested, play back tokens smoothly at 60 FPS
    if getattr(req, "stream", False):
        from src.api.routers.chat_streaming import create_cached_sse_stream
        return create_cached_sse_stream(res_dict, request, session_id, request_id, rate_headers)

    # Non-streaming JSON response
    return JSONResponse(
        content=res_dict,
        headers={
            "X-Slash-Command": cmd_res.command,
            "X-Process-Time-Ms": str(round(cmd_res.execution_time * 1000, 1)),
            **rate_headers,
        },
    )
