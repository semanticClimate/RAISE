"""

RAISE (Research Assessment Intelligence & Semantic Extraction)

Tier 1: Cloudflare Gateway & Edge Host (server.py)

===================================================

Master application server providing:

1. Subprocess Tunnel Watchdog (cloudflared) with Windows group isolation

2. Pre-flight Port Sweep (Port 8000 zombie cleaner)

3. Pure ASGI Security Shield with O(1) Redis Blacklisting (blacklist:ip:{ip})

4. Upload Memory Safeguard (bypasses body capture on multipart/upload paths)

5. Two-Step WebSocket & SSE Ephemeral Token Handshake with Atomic Eviction

6. Live Terminal Edge Monitor (Client IP, Location, Ray-ID, Device, Query, Latency)

7. Mounts core GraphRAG routes (/api/chat, /api/documents, /api/health)

"""



from __future__ import annotations



import os

import sys

# Enforce UTF-8 console output for Windows terminal and log redirection

if hasattr(sys.stdout, "reconfigure"):

    try:

        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    except Exception:

        pass

if hasattr(sys.stderr, "reconfigure"):

    try:

        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    except Exception:

        pass



import time

import json

import asyncio

import logging

from contextlib import asynccontextmanager

from pathlib import Path

from typing import Optional, Set, Dict, Any



# Windows Asyncio Proactor ConnectionResetError [WinError 10054] mitigation

if sys.platform == "win32":

    try:

        from asyncio.proactor_events import _ProactorBasePipeTransport

        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost



        def _silenced_call_connection_lost(self, exc):

            try:

                _orig_call_connection_lost(self, exc)

            except (ConnectionResetError, OSError):

                pass



        _ProactorBasePipeTransport._call_connection_lost = _silenced_call_connection_lost

    except Exception:

        pass



from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status

from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.gzip import GZipMiddleware

from starlette.websockets import WebSocketState
import uuid
from src.core.telemetry_bus import get_telemetry_bus, install_telemetry_hooks

import redis.asyncio as aioredis



# Ensure RAG dir in sys.path

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:

    sys.path.insert(0, str(BASE_DIR))



# Load environment

try:

    from dotenv import load_dotenv

    _env_file = BASE_DIR / ".env"

    if _env_file.exists():

        load_dotenv(dotenv_path=_env_file)

    else:

        load_dotenv()

except Exception:

    pass



# Logging configuration

logging.basicConfig(

    level=os.getenv("LOG_LEVEL", "INFO").upper(),

    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",

    stream=sys.stdout,

)

logger = logging.getLogger("RAISE.Server")





class PrivacyPathFilter(logging.Filter):

    """Dynamically redacts host user directories and repo absolute paths from log outputs."""

    def __init__(self):

        super().__init__()

        self.home_win = str(Path.home())

        self.home_unix = self.home_win.replace("\\", "/")

        try:

            self.repo_root = str(Path(__file__).resolve().parent.parent)

            self.repo_root_unix = self.repo_root.replace("\\", "/")

        except Exception:

            self.repo_root = ""

            self.repo_root_unix = ""



    def filter(self, record: logging.LogRecord) -> bool:

        if isinstance(record.msg, str):

            if self.repo_root:

                record.msg = record.msg.replace(self.repo_root, ".").replace(self.repo_root_unix, ".")

            record.msg = record.msg.replace(self.home_win, "~").replace(self.home_unix, "~")

        if record.args:

            if isinstance(record.args, tuple):

                new_args = []

                for a in record.args:

                    if isinstance(a, str):

                        if self.repo_root:

                            a = a.replace(self.repo_root, ".").replace(self.repo_root_unix, ".")

                        a = a.replace(self.home_win, "~").replace(self.home_unix, "~")

                    new_args.append(a)

                record.args = tuple(new_args)

        return True





logging.root.addFilter(PrivacyPathFilter())



# Suppress informational notifications from Neo4j driver

logging.getLogger("neo4j").setLevel(logging.WARNING)

logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)



# Import Security Package

from src.security import (

    resolve_client_ip,

    PortSweep,

    SubprocessTunnelManager,

    PureASGISecurityShieldMiddleware,

    HandshakeManager,

)



# Global Manager Handles

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

APP_PORT = int(os.getenv("PORT", "8000"))

APP_HOST = os.getenv("HOST", "0.0.0.0")



redis_client: Optional[aioredis.Redis] = None

handshake_mgr: Optional[HandshakeManager] = None

tunnel_mgr: Optional[SubprocessTunnelManager] = None

active_ws_subscribers: Set[WebSocket] = set()

ws_session_tokens: Dict[WebSocket, str] = {}

ws_session_ips: Dict[WebSocket, str] = {}

pubsub_listener_task: Optional[asyncio.Task] = None





async def listen_admin_and_telemetry_pubsub(r: aioredis.Redis):

    """

    Subscribes to Redis Pub/Sub channels to:

    1. Distribute telemetry frames to local WebSocket connections

    2. Handle administrative SESSION_KICK and IP_BLOCK teardown signals

    """

    pubsub = r.pubsub()

    await pubsub.subscribe("channel:telemetry:updates", "channel:admin:session_controls")

    logger.info("Subscribed to Redis channels: telemetry updates & admin controls.")



    try:

        async for message in pubsub.listen():

            if message["type"] != "message":

                continue

            channel = message["channel"]

            if isinstance(channel, bytes):

                channel = channel.decode("utf-8")

            data_str = message["data"]

            if isinstance(data_str, bytes):

                data_str = data_str.decode("utf-8")



            try:

                event_data = json.loads(data_str)

            except Exception:

                continue



            # Channel 1: Admin session controls (Kick / Block)

            if channel == "channel:admin:session_controls":

                evt = event_data.get("event")

                target = event_data.get("target")

                evt_type = event_data.get("type")



                if evt_type == "SESSION_KICK" or evt == "session_revoked":

                    # Scan local active websockets and disconnect matching token

                    for ws, token in list(ws_session_tokens.items()):

                        if token == target:

                            logger.warning(f"Admin KICK executed on local session {token[:8]}...")

                            try:

                                await ws.close(code=4403, reason="Session terminated by Administrator.")

                            except Exception:

                                pass

                            active_ws_subscribers.discard(ws)

                            ws_session_tokens.pop(ws, None)

                            ws_session_ips.pop(ws, None)



                elif evt_type == "IP_BLOCK":

                    # Disconnect all active websockets from that IP

                    for ws, ip in list(ws_session_ips.items()):

                        if ip == target:

                            logger.warning(f"Admin IP_BLOCK executed on local socket IP {ip}")

                            try:

                                await ws.close(code=4403, reason="IP Blocked by Administrator.")

                            except Exception:

                                pass

                            active_ws_subscribers.discard(ws)

                            ws_session_tokens.pop(ws, None)

                            ws_session_ips.pop(ws, None)



            # Channel 2: Telemetry Updates

            elif channel == "channel:telemetry:updates":

                frame_payload = {"type": "log_frame", "data": event_data}

                # Log live telemetry frame to server terminal

                _print_live_edge_monitor(event_data)



                for ws in list(active_ws_subscribers):

                    if ws.client_state == WebSocketState.CONNECTED:

                        try:

                            await ws.send_json(frame_payload)

                        except Exception:

                            active_ws_subscribers.discard(ws)

                            ws_session_tokens.pop(ws, None)

                            ws_session_ips.pop(ws, None)



    except asyncio.CancelledError:

        try:

            await pubsub.unsubscribe("channel:telemetry:updates", "channel:admin:session_controls")

        except Exception:

            pass

        try:

            if hasattr(pubsub, "aclose"):

                await pubsub.aclose()

            else:

                await pubsub.close()

        except Exception:

            pass





def _print_live_edge_monitor(event_data: Dict[str, Any]):

    """Renders formatted live edge monitor terminal logs for multi-user connections."""

    try:

        _safe_print_live_edge_monitor(event_data)

    except Exception:

        pass



_POLL_PATHS = {
    "/api/health",
    "/api/system/routing",
    "/api/system/hardware",
    "/api/system/config",
    "/api/system/diagnostics",
    "/api/documents",
    "/api/commands",
    "/api/telemetry",
    "/favicon.ico",
}
_LOCAL_IPS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _safe_print_live_edge_monitor(event_data: Dict[str, Any]):
    path = event_data.get("path", "/")
    if not path.startswith("/api"):
        return

    method = event_data.get("method", "GET")
    client_ip = event_data.get("client_ip", "127.0.0.1")

    # Mute noisy periodic background polls from local frontend / supervisor
    if method == "GET" and (client_ip in _LOCAL_IPS or client_ip.startswith("127.")):
        if any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in _POLL_PATHS):
            return

    status_code = event_data.get("status", 200)
    duration_ms = event_data.get("duration_ms", 0.0)
    req_body = event_data.get("request_body", "")

    ts = time.strftime("%H:%M:%S", time.localtime(event_data.get("timestamp", time.time())))
    sym = "\u2713" if 200 <= status_code < 400 else "\u2715"
    color = "\033[92m" if 200 <= status_code < 400 else "\033[91m"
    ip_disp = "local" if (client_ip in _LOCAL_IPS or client_ip.startswith("127.")) else client_ip

    print(f"  \033[90m[{ts}]\033[0m {color}{sym}\033[0m \033[1m{method} {path}\033[0m \033[90m\u2192\033[0m {color}{status_code}\033[0m \033[90m({duration_ms:.1f}ms \u2022 {ip_disp})\033[0m")
    if req_body and req_body != "[MULTIPART_UPLOAD_BYPASS]":
        preview = req_body[:100].replace("\n", " ").strip()
        if preview:
            print(f"       \033[90m\u2514\u2500 {preview}\033[0m")





_forwarder_task: Optional[asyncio.Task] = None


async def _forward_telemetry_bus_to_websockets():
    bus = get_telemetry_bus()
    queue = asyncio.Queue(maxsize=1000)
    bus.subscribe_async(queue)
    try:
        while True:
            event = await queue.get()
            payload = {"type": event.event_type, "data": event.data, "ts": event.ts}
            for ws in list(active_ws_subscribers):
                if ws.client_state == WebSocketState.CONNECTED:
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        active_ws_subscribers.discard(ws)
    except asyncio.CancelledError:
        bus.unsubscribe_async(queue)


@asynccontextmanager

async def server_lifespan(app: FastAPI):

    """

    Master Lifespan Manager:

    1. Pre-flight Port Sweep

    2. Redis Client & Pub/Sub Initialized

    3. Cloudflare Tunnel Manager Started

    4. Clean Teardown Protocol on Shutdown

    """

    global redis_client, handshake_mgr, tunnel_mgr, pubsub_listener_task, _forwarder_task
    install_telemetry_hooks()
    _forwarder_task = asyncio.create_task(_forward_telemetry_bus_to_websockets())



    # Mute noisy third-party loggers during model pre-warming and request servicing
    for logger_name in ("httpx", "httpcore", "urllib3", "huggingface_hub", "transformers"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    print(f"  \033[1;92m\u2713\033[0m \033[1mRAISE Edge Gateway\033[0m \033[90m\u2022\033[0m \033[96mhttp://localhost:{APP_PORT}\033[0m \033[90m(Swagger: /docs)\033[0m")



    # 1. Pre-flight Port Sweep

    logger.info(f"Running pre-flight port sweep on port {APP_PORT}...")

    port_freed = await asyncio.to_thread(PortSweep.sweep_and_clean, APP_PORT)

    if not port_freed:

        logger.warning(f"Port {APP_PORT} check completed with potential conflict.")



    # 2. Redis Connection (Fail-fast with 250ms timeout)

    enable_redis = os.getenv("ENABLE_REDIS", "true").lower() in ("true", "1")

    if enable_redis:

        try:

            redis_client = aioredis.from_url(

                REDIS_URL,

                decode_responses=False,

                socket_connect_timeout=0.25,

                socket_timeout=0.25,

            )

            await asyncio.wait_for(redis_client.ping(), timeout=0.3)

            logger.info(f"Connected to Redis at {REDIS_URL}")

            app.state.redis = redis_client

            handshake_mgr = HandshakeManager(redis_client)

            app.state.handshake_mgr = handshake_mgr

            

            # Start Pub/Sub background listener

            pubsub_listener_task = asyncio.create_task(listen_admin_and_telemetry_pubsub(redis_client))

        except Exception as e:

            logger.warning(f"Redis unavailable ({e}). Telemetry caching and handshake will run in standalone mode.")

            redis_client = None

            handshake_mgr = None

    else:

        logger.info("Redis disabled via ENABLE_REDIS=false. Running in standalone mode.")

        redis_client = None

        handshake_mgr = None



    # Start middleware background telemetry queue worker

    if hasattr(app.state, "asgi_shield"):

        app.state.asgi_shield.redis = redis_client

        app.state.asgi_shield.start_background_worker()



    # 3. Subprocess Tunnel Watchdog (Optional, default disabled for direct local operation)

    enable_tunnel = (

        (os.getenv("ENABLE_CLOUDFLARE_TUNNEL", "false").lower() in ("true", "1") or "--tunnel" in sys.argv)

        and ("--no-tunnel" not in sys.argv)

    )

    if enable_tunnel:

        logger.info("Initializing Cloudflare Tunnel Watchdog...")

        tunnel_mgr = SubprocessTunnelManager(port=APP_PORT)

        app.state.tunnel_mgr = tunnel_mgr

        tunnel_url = await tunnel_mgr.start()

        if tunnel_url:

            print("\033[1;92m" + "─" * 78 + "\033[0m")

            print(f" \033[1;92m🌐 PUBLIC EDGE TUNNEL ACTIVE:\033[0m \033[1;96m{tunnel_url}\033[0m")

            print(f" \033[90mTunnel routes securely to local backend at http://localhost:{APP_PORT}\033[0m")

            print("\033[1;92m" + "─" * 78 + "\033[0m")

    else:
        logger.info(f"Local gateway active on http://localhost:{APP_PORT}")



    # 4 & 5. Sequenced Background Startup: Pre-warm shared models, then synchronize documents
    app.state.neural_ready = False
    app.state.neural_error = None

    async def _startup_background_tasks():
        try:
            logger.info("Starting neural models pre-warming (embeddings, reranker, NLI)...")
            from src.infrastructure.model_warmup import warmup_all_neural_models
            rag_eng = getattr(app.state, "rag_engine", None)
            await asyncio.to_thread(warmup_all_neural_models, False, rag_eng)
            app.state.neural_ready = True
            logger.info("Neural models pre-warming completed successfully.")
        except Exception as exc:
            logger.warning(f"Neural models pre-warming encountered an issue: {exc}")
            app.state.neural_error = str(exc)
            app.state.neural_ready = True

        if hasattr(app.state, "dev_operator") and app.state.dev_operator:
            try:
                await asyncio.to_thread(app.state.dev_operator.auto_synchronize_pending_documents)
            except Exception as exc:
                logger.warning(f"Startup document synchronization notice in server.py: {exc}")

    asyncio.create_task(_startup_background_tasks())



    yield



    # Shutdown Phase

    logger.info("Shutting down RAISE Gateway...")



    if pubsub_listener_task and not pubsub_listener_task.done():

        pubsub_listener_task.cancel()

        try:

            await pubsub_listener_task

        except (asyncio.CancelledError, Exception):

            pass



    if _forwarder_task and not _forwarder_task.done():
        _forwarder_task.cancel()
        try:
            await _forwarder_task
        except (asyncio.CancelledError, Exception):
            pass

    if hasattr(app.state, "asgi_shield"):

        await app.state.asgi_shield.stop_background_worker()



    if tunnel_mgr:

        await tunnel_mgr.stop()



    if redis_client:

        try:

            if hasattr(redis_client, "aclose"):

                await redis_client.aclose()

            else:

                await redis_client.close()

        except Exception:

            pass



    logger.info("RAISE Gateway teardown complete.")





# Initialize FastAPI App

app = FastAPI(

    title="RAISE Master Edge Gateway",

    version="1.0.0",

    description="Enterprise edge gateway for Research Assessment Intelligence & Semantic Extraction",

    lifespan=server_lifespan

)



app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

    max_age=3600,

)



app.add_middleware(PureASGISecurityShieldMiddleware, fastapi_app=app)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def telemetry_http_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]
    origin = "TUI" if "RAISE-TUI" in request.headers.get("User-Agent", "") else "BROWSER"
    client_ip = resolve_client_ip(dict(request.scope))

    bus = get_telemetry_bus()
    t0 = time.perf_counter()
    bus.emit_http_request(
        method=request.method,
        path=request.url.path,
        origin=origin,
        request_id=req_id,
        client_ip=client_ip,
        user_agent=request.headers.get("User-Agent", ""),
    )

    response = None
    err_str = None
    try:
        response = await call_next(request)
        return response
    except Exception as ex:
        err_str = str(ex)
        raise
    finally:
        duration_ms = (time.perf_counter() - t0) * 1000
        status_code = response.status_code if response else 500
        payload_bytes = 0
        if response and "content-length" in response.headers:
            try:
                payload_bytes = int(response.headers["content-length"])
            except Exception:
                pass

        bus.emit_http_response(
            method=request.method,
            path=request.url.path,
            origin=origin,
            request_id=req_id,
            status_code=status_code,
            duration_ms=duration_ms,
            payload_bytes=payload_bytes,
            error=err_str,
        )
        if response:
            response.headers["X-Request-Id"] = req_id


# Handshake endpoints are mounted from core_rag_app (app.py) at the bottom of this file
# to prevent duplicate route definitions and duplicate OpenAPI operation IDs.

# ------------------------------------------------------------------------------
# WebSocket Telemetry Stream (Two-Step Handshake Verification + Local Dev Fallback)
# ------------------------------------------------------------------------------

@app.websocket("/ws/traffic")
@app.websocket("/ws/telemetry")
async def websocket_traffic_endpoint(websocket: WebSocket):
    query_params = websocket.query_params
    token = query_params.get("token")
    client_ip = resolve_client_ip(dict(websocket.scope))
    is_local = client_ip in ("127.0.0.1", "::1", "localhost", "testclient") or client_ip.startswith("127.")

    if not token and not is_local:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication handshake token.")
        return

    mgr: Optional[HandshakeManager] = getattr(app.state, "handshake_mgr", None)
    if token and mgr and mgr.redis:
        is_blocked = await mgr.is_ip_blocked(client_ip)
        if is_blocked:
            await websocket.close(code=4403, reason="ERR_BLOCKED_IP: Client IP is blacklisted.")
            return

        if not is_local:
            session_data = await mgr.verify_and_consume_token(token, client_ip=client_ip)
            if not session_data:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or already consumed handshake token.")
                return

    await websocket.accept()
    active_ws_subscribers.add(websocket)
    ws_session_tokens[websocket] = token or "local_dev"
    ws_session_ips[websocket] = client_ip
    logger.info(f"WebSocket client connected from {client_ip} (active subscribers: {len(active_ws_subscribers)})")

    # Send initial welcome frame
    await websocket.send_json({
        "type": "connection_ready",
        "client_ip": client_ip,
        "session_token_prefix": ((token[:8] + "...") if token else "local_dev"),
        "timestamp": time.time(),
        "stats": get_telemetry_bus().get_snapshot(),
    })

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                continue
            try:
                msg = json.loads(data)
                msg_type = msg.get("type") or msg.get("subtype") or "browser_event"
                level = msg.get("level") or "INFO"
                text = msg.get("message") or msg.get("details") or str(msg)
                get_telemetry_bus().emit_browser_event(
                    source="WS",
                    event_subtype=str(msg_type),
                    level=str(level),
                    message=str(text),
                    details=msg,
                )
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as err:
        logger.debug(f"WebSocket disconnect: {err}")
    finally:
        active_ws_subscribers.discard(websocket)
        ws_session_tokens.pop(websocket, None)
        ws_session_ips.pop(websocket, None)
        logger.info(f"WebSocket disconnected (remaining: {len(active_ws_subscribers)})")


@app.post("/api/telemetry/browser")
async def browser_telemetry_beacon(request: Request):
    """Fallback HTTP endpoint for navigator.sendBeacon and client error logging."""
    try:
        body = await request.json()
        bus = get_telemetry_bus()
        if isinstance(body, list):
            for item in body:
                if isinstance(item, dict):
                    bus.emit_browser_event(
                        source="HTTP_BEACON",
                        event_subtype=item.get("type", "log"),
                        level=item.get("level", "INFO"),
                        message=item.get("message", str(item)),
                        details=item,
                    )
        elif isinstance(body, dict):
            bus.emit_browser_event(
                source="HTTP_BEACON",
                event_subtype=body.get("type", "log"),
                level=body.get("level", "INFO"),
                message=body.get("message", str(body)),
                details=body,
            )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

        ws_session_tokens.pop(websocket, None)

        ws_session_ips.pop(websocket, None)

        logger.info(f"WebSocket disconnected (remaining: {len(active_ws_subscribers)})")





# ------------------------------------------------------------------------------
# Readiness Probe (Tracks Neural Model Pre-warming State)
# ------------------------------------------------------------------------------
@app.get("/api/ready")
@app.get("/ready")
async def check_neural_readiness(request: Request):
    from src.infrastructure.model_warmup import is_neural_stack_ready
    is_ready = getattr(request.app.state, "neural_ready", False) or is_neural_stack_ready()
    return {
        "status": "ready" if is_ready else "warming_up",
        "ready": is_ready,
        "error": getattr(request.app.state, "neural_error", None),
    }


@app.get("/api/provenance")
@app.get("/provenance")
async def get_provenance_metadata(mode: Optional[str] = "expert"):
    from src.infrastructure.provenance import build_pipeline_info
    return build_pipeline_info(mode=mode)


# ------------------------------------------------------------------------------
# Mount Core RAISE Application Routes from app.py
# ------------------------------------------------------------------------------

try:

    import app as rag_app_module

    core_rag_app = rag_app_module.app

    # Mount all routes from core_rag_app

    app.include_router(core_rag_app.router)

    # Forward core singletons to gateway app.state so router handlers receive live instances

    for key in [

        "rag_engine",

        "postgres_manager",

        "redis_cache",

        "dev_operator",

        "session_memory_manager",

        "session_service",

        "document_service",

        "chat_service",

        "query_service",

    ]:

        val = getattr(core_rag_app.state, key, None) or getattr(rag_app_module, key, None)

        if val is not None:

            setattr(app.state, key, val)

    # Forward unified exception handlers

    app.exception_handlers.update(core_rag_app.exception_handlers)

    logger.info("Successfully mounted all core RAISE GraphRAG routes from app.py and forwarded singletons")

except Exception as e:

    logger.warning(f"Could not import routes from app.py directly: {e}. Adding fallback routes.")



    @app.get("/api/health")
    async def fallback_health():
        return {"status": "ok", "service": "RAISE Master Gateway", "timestamp": time.time()}





# System Info / Diagnostic Endpoint

@app.get("/api/info")

@app.get("/api/status")

async def root_gateway_status():

    return {

        "name": "RAISE (Research Assessment Intelligence & Semantic Extraction)",

        "role": "Cloudflare Gateway & Live Edge Host",

        "version": "1.0.0",

        "status": "operational",

        "subsystems": {

            "neo4j": "bolt://localhost:7687",

            "redis": REDIS_URL,

            "port": APP_PORT,

            "tunnel_active": tunnel_mgr is not None and tunnel_mgr.public_url is not None

        }

    }





# Check for production frontend distribution

_dist_candidates = [

    BASE_DIR / "frontend" / "dist",

    BASE_DIR.parent / "frontend" / "dist",

    BASE_DIR / "dist",

    BASE_DIR / "static",

    Path("/app/frontend/dist"),

    Path("/app/dist"),

]

_dist_dir = next((p for p in _dist_candidates if p.is_dir() and (p / "index.html").is_file()), None)



if _dist_dir:

    from fastapi.staticfiles import StaticFiles

    from fastapi.responses import FileResponse

    from starlette.responses import JSONResponse



    _assets_dir = _dist_dir / "assets"

    if _assets_dir.is_dir():

        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="frontend_assets")

    # Ensure root '/' serves the SPA index.html instead of any prior default API root route
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/"]

    @app.get("/", include_in_schema=False)
    async def serve_spa_root():
        return FileResponse(_dist_dir / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)

    async def serve_spa_frontend(full_path: str):

        # Allow API, WS, Swagger docs and OpenAPI schema to fall through to their handlers

        if full_path.startswith(("api/", "api", "ws/", "ws", "docs", "redoc", "openapi.json")):

            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # Guard: Do not serve index.html for missing /assets/* static files (prevents browser SyntaxError: Unexpected token \'<\')
        if full_path.startswith("assets/"):
            return JSONResponse(status_code=404, content={"detail": "Asset not found"})
        target_path = _dist_dir / full_path

        if full_path and target_path.is_file():

            return FileResponse(target_path)

        return FileResponse(_dist_dir / "index.html")

    logger.info("Mounted production frontend from: %s", _dist_dir)

else:

    @app.get("/")

    async def root_gateway_index():

        return await root_gateway_status()





if __name__ == "__main__":

    if "--no-tunnel" in sys.argv:

        os.environ["ENABLE_CLOUDFLARE_TUNNEL"] = "false"

        sys.argv.remove("--no-tunnel")

    import uvicorn

    try:

        uvicorn.run(app, host=APP_HOST, port=APP_PORT, reload=False, log_level="info")

    except (KeyboardInterrupt, SystemExit):

        logger.info("Server process stopped gracefully.")

