"""
RAISE — Service Supervisor & Interactive Console
=================================================
Architecture:
1. Orchestrates FastAPI Backend (:8000) and React/Vite Frontend (:5173).
2. Zero-delay unbuffered live telemetry stream with timestamped badges.
3. Non-blocking pinned bottom prompt bar with automatic redraw lock.
4. Real-time hardware, database substrate, and neural pipeline cards.
5. Robust signal handling and automatic port cleanup on shutdown.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

# Ensure UTF-8 unbuffered console output for zero-latency streaming
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", write_through=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", write_through=True)

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

from src.cli.renderer import C
from src.cli.document_manager import get_active_documents_list
from src.cli.system_launcher import get_synthesizer_status
from src.core.config import models
from src.core.substrate_router import get_substrate_telemetry_summary, get_active_substrate_mode, SubstrateMode

logger = logging.getLogger("RAISE_ServiceRunner")

# ==============================================================================
# Prompt Synchronization & Terminal Stream Engine
# ==============================================================================

_console_lock = threading.Lock()
_active_repl_prompt: Optional[str] = None
_active_prompt_header: Optional[str] = None

B_DIM = "\033[38;5;240m"
B_TXT = "\033[38;5;248m"
W_WIDTH = 76


def _now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def format_stream_row(tag: str, message: str, icon: str = "\u25cf", tag_color: str = C.CYAN, msg_color: str = C.WHITE) -> str:
    """Formats a single live telemetry line in column format."""
    ts = _now_ts()
    tag_padded = f"{tag:<8}"[:8]
    return f"  {B_DIM}│{C.RESET} {C.MUTED}{ts}{C.RESET} {B_DIM}│{C.RESET} {tag_color}{tag_padded}{C.RESET} {B_DIM}│{C.RESET} {icon} {msg_color}{message}{C.RESET}"


def print_supervisor_event(text: str) -> None:
    """
    Immediately flushes a real-time event above the pinned bottom input bar
    without breaking or mangling the user's active typing line.
    """
    with _console_lock:
        global _active_repl_prompt, _active_prompt_header
        if _active_repl_prompt and _active_prompt_header:
            sys.stdout.write(f"\r\033[1A\033[J{text}\n{_active_prompt_header}\n{_active_repl_prompt}")
            sys.stdout.flush()
        elif _active_repl_prompt:
            sys.stdout.write(f"\r\033[K{text}\n{_active_repl_prompt}")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"{text}\n")
            sys.stdout.flush()


# ==============================================================================
# Helper Utilities & Port Management
# ==============================================================================

def sanitize_text(text: str) -> str:
    """Sanitizes user home paths for privacy in console logs."""
    if not text:
        return text
    user_home = str(Path.home())
    return text.replace(user_home, "~").replace(user_home.replace("\\", "/"), "~")


def free_port(port: int) -> None:
    """Terminates any process listening on the given TCP port on Windows."""
    try:
        cmd = f'netstat -ano | findstr ":{port} "'
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        pids = set()
        for line in proc.stdout.splitlines():
            line = line.strip()
            if "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != os.getpid():
                        pids.add(int(pid))
        for p in pids:
            try:
                subprocess.run(f"taskkill /PID {p} /T /F", shell=True, capture_output=True, timeout=5)
            except Exception:
                pass
    except Exception:
        pass


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Checks if a TCP port is open and listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ==============================================================================
# Subsystem Diagnostics & Status Dashboard
# ==============================================================================

def fetch_json_endpoint(url: str, timeout: float = 3.0) -> Optional[Dict[str, Any]]:
    """Safely retrieves JSON response from an HTTP endpoint."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RAISE-Diagnostics"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def print_banner() -> None:
    """Renders the top-level RAISE banner."""
    print(f"\n  {C.TITLE}RAISE ACADEMIC GRAPHRAG STUDIO{C.RESET} {B_DIM}//{C.RESET} {C.CYAN}MONOREPO PLATFORM{C.RESET}")
    print(f"  {C.MUTED}Backend API : http://localhost:8000 (Swagger: /docs)   \u2022   Frontend UI : http://localhost:5173{C.RESET}\n")


def _render_status_dashboard(focused_doc: Optional[str] = None) -> None:
    """Renders real-time diagnostic dashboard with Unicode tree geometry."""
    print(f"\n  {B_DIM}╭{'─' * W_WIDTH}╮{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.TITLE}RAISE SYSTEM HEALTH & SUBSYSTEM DIAGNOSTICS{C.RESET}{' ' * 32}{B_DIM}│{C.RESET}")
    print(f"  {B_DIM}├{'─' * W_WIDTH}┤{C.RESET}")

    # 1. Hardware Summary
    hw = fetch_json_endpoint("http://127.0.0.1:8000/api/system/hardware", timeout=1.5)
    if hw:
        cuda_active = bool(hw.get("has_metal_or_cuda") or hw.get("cuda_available") or hw.get("gpu_detected"))
        vram = hw.get("vram_gb") or hw.get("gpu_vram_gb", 0)
        raw_gpu = hw.get("gpu")
        gpu_name = hw.get("gpu_name") or (raw_gpu.get("details") if isinstance(raw_gpu, dict) else "None")
        gpu_str = f"{gpu_name} ({float(vram):.1f}GB VRAM)" if (cuda_active and gpu_name and gpu_name != "None") else "CPU Only (CUDA Inactive)"
        avail_ram = hw.get("free_ram_gb") or hw.get("ram_available_gb") or hw.get("available_ram_gb", 0)
        tot_ram = hw.get("total_ram_gb") or hw.get("ram_total_gb", 0)
        ram_str = f"{float(avail_ram):.1f} / {float(tot_ram):.1f} GB"
        cpu_cnt = hw.get("cpu_cores") or hw.get("cpu_count", 0)
        hw_line = f"GPU: {gpu_str}  •  RAM: {ram_str} ({cpu_cnt} Cores)"
    else:
        try:
            import psutil
            ram = psutil.virtual_memory()
            ram_str = f"{ram.available / (1024**3):.1f} / {ram.total / (1024**3):.1f} GB"
            cpu_cnt = os.cpu_count() or 4
            gpu_str = "CPU Only"
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
                    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
                    gpu_str = f"{gpu_name} ({vram_gb}GB VRAM)"
            except Exception:
                pass
            hw_line = f"GPU: {gpu_str}  •  RAM: {ram_str} ({cpu_cnt} Cores)"
        except Exception:
            hw_line = "Hardware telemetry active"

    sub_info = get_substrate_telemetry_summary(
        neo4j_open=is_port_open(7687),
        redis_open=is_port_open(6379),
        pg_open=is_port_open(5432),
    )
    print(f"  {B_DIM}│{C.RESET} {C.SECTION}SUBSTRATE{C.RESET}  {C.ACCENT}{sub_info['mode_badge']}{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.SECTION}HARDWARE{C.RESET}   {C.WHITE}{hw_line}{C.RESET}")
    print(f"  {B_DIM}├{'─' * W_WIDTH}┤{C.RESET}")

    # 2. Subsystems
    cfg = fetch_json_endpoint("http://127.0.0.1:8000/api/system/config", timeout=1.5) or {}
    prov = fetch_json_endpoint("http://127.0.0.1:8000/api/system/provenance", timeout=1.5) or {}
    routing = fetch_json_endpoint("http://127.0.0.1:8000/api/system/routing", timeout=1.5) or {}
    synth = get_synthesizer_status()

    chroma_count = 0
    chroma_model = models.EMBEDDING_MODEL_NAME
    chroma_online = False
    try:
        import chromadb
        repo_root = BASE_DIR.parent if BASE_DIR.name == "backend" else BASE_DIR
        candidates = [
            repo_root / "backend" / ".chromadb_embeddinggemma_2",
            repo_root / "backend" / ".chromadb_bge_large",
            BASE_DIR / ".chromadb_embeddinggemma_2",
            BASE_DIR / ".chromadb_bge_large",
        ]
        target_chroma = next((p for p in candidates if p.exists()), None)
        if target_chroma:
            client = chromadb.PersistentClient(path=str(target_chroma))
            cols = client.list_collections()
            chroma_count = sum(c.count() for c in cols)
            chroma_model = models.EMBEDDING_MODEL_NAME if models.EMBEDDING_MODEL_KEYWORD in target_chroma.name else models.EMBEDDING_FALLBACK_MODEL_NAME
            chroma_online = True
    except Exception:
        pass

    neo4j_online = is_port_open(7687)
    neo4j_str = f"{C.SUCCESS}\u2713 CONNECTED{C.RESET} (bolt://localhost:7687)" if neo4j_online else f"{C.WARN}\u25cf STANDBY{C.RESET}   (In-memory NetworkX active)"

    redis_online = is_port_open(6379)
    redis_str = f"{C.SUCCESS}\u2713 CONNECTED{C.RESET} (localhost:6379)" if redis_online else f"{C.MUTED}\u25cf STANDBY{C.RESET}   (In-memory LRU active)"

    pg_online = is_port_open(5432)
    pg_str = f"{C.SUCCESS}\u2713 CONNECTED{C.RESET} (localhost:5432)" if pg_online else f"{C.MUTED}\u25cf STANDBY{C.RESET}   (SQLite local persistence)"

    chroma_str = f"{C.SUCCESS}\u2713 ACTIVE{C.RESET}    ({chroma_count} chunks | {chroma_model})" if chroma_online else f"{C.WARN}\u25cf STANDBY EMPTY / OFFLINE{C.RESET}"
    synth_raw = synth.get("display_string", f"{C.SUCCESS}\u2713 ACTIVE{C.RESET}")
    synth_str = synth_raw.replace("\u2714", "\u2713").replace("\u2716", "\u2715")

    encoder_name = prov.get("encoder_model") or cfg.get("embedding_model") or chroma_model
    reranker_name = prov.get("reranker_model") or cfg.get("reranker_model") or models.RERANKER_MODEL_NAME
    nli_name = prov.get("nli_verifier_model") or cfg.get("nli_verifier_model") or models.NLI_MODEL_NAME

    print(f"  {B_DIM}│{C.RESET} {C.SECTION}CONNECTION & NETWORK TOPOLOGY{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Backend API Gateway      {C.WHITE}http://localhost:8000{C.RESET}  {C.MUTED}(Swagger: {C.CYAN}/docs{C.MUTED}){C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Frontend UI              {C.WHITE}http://localhost:5173{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} Live Telemetry Socket    {C.WHITE}ws://localhost:8000/ws/traffic{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.SECTION}STORAGE & DATABASE SUBSTRATES{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Vector Store (ChromaDB)  {chroma_str}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Knowledge Graph Engine   {C.SUCCESS}{sub_info['neo4j']}{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Semantic Cache           {C.SUCCESS}{sub_info['redis']}{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Relational Database      {C.SUCCESS}{sub_info['postgres']}{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} Document Vault Storage   {C.CYAN}{sub_info['storage']}{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}")
    routing_chain = routing.get("fallback_chain") or []
    policy_label = routing.get("routing_policy") or ("LOCAL_FIRST" if synth.get("type") == "local" else "CLOUD_FIRST")
    if routing_chain:
        chain_display = " -> ".join(p.upper() for p in routing_chain[:4])
        priority_str = f"{C.WHITE}{chain_display}{C.RESET} {C.MUTED}({policy_label}){C.RESET}"
    else:
        prim = (synth.get("provider") or "AUTO").upper()
        priority_str = f"{C.WHITE}{prim}{C.RESET} {C.MUTED}({policy_label}){C.RESET}"

    print(f"  {B_DIM}│{C.RESET} {C.SECTION}AI NEURAL MODEL PIPELINE{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Active LLM Priority      {priority_str}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Synthesis LLM Engine     {synth_str}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Dense Embedding Encoder  {C.WHITE}{encoder_name}{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} Cross-Attention Reranker {C.WHITE}{reranker_name}{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} Claim Entailment (NLI)   {C.WHITE}{nli_name}{C.RESET}")

    docs = get_active_documents_list()
    print(f"  {B_DIM}│{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.SECTION}REGISTERED DOCUMENT LIBRARY ({len(docs)} documents){C.RESET}")
    if docs:
        visible_docs = docs[:8]
        for idx, d in enumerate(visible_docs, 1):
            branch = "╰─" if (idx == len(visible_docs) and len(docs) <= 8) else "├─"
            fn = d.get("filename", "document.pdf")
            short_fn = fn if len(fn) <= 38 else fn[:35] + "..."
            pgs = d.get("pages", 0)
            chks = d.get("chunks_count", 0)
            sz = f"{d.get('size_mb', 0):.1f}MB"
            print(f"  {B_DIM}│{C.RESET}  {B_DIM}{branch}{C.RESET} [{C.NUM}{idx}{C.RESET}] {C.WHITE}{short_fn:<38}{C.RESET} {C.NUM}{pgs:>3}p{C.RESET} {B_DIM}│{C.RESET} {C.NUM}{chks:>4} chks{C.RESET} {B_DIM}│{C.RESET} {sz:>7}")
        if len(docs) > 8:
            print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} {C.MUTED}... and {len(docs) - 8} more documents (type 'docs' to view all){C.RESET}")
    else:
        print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} {C.WARN}⚠️  No documents in catalog. Upload PDFs via Web UI or 'upload <path>'{C.RESET}")

    scope_name = f"'{focused_doc}' (Single Document Target)" if focused_doc else "ALL REGISTERED DOCUMENTS (Multi-Hop Graph Scope)"
    print(f"  {B_DIM}│{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.SECTION}INTERACTIVE CONSOLE SCOPE{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} Active Research Scope    {C.ACCENT}{scope_name}{C.RESET}")
    print(f"  {B_DIM}╰{'─' * W_WIDTH}╯{C.RESET}\n")


def print_live_status_dashboard(focused_doc: Optional[str] = None) -> None:
    """Thread-safe entrypoint ensuring the dashboard is never mangled by background events."""
    with _console_lock:
        _render_status_dashboard(focused_doc)


def run_system_doctor() -> None:
    """Executes end-to-end diagnostic probes on all endpoints and services."""
    print(f"\n  {B_DIM}╭{'─' * W_WIDTH}╮{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.TITLE}🩺 RAISE SYSTEM DOCTOR — FORENSIC ENDPOINT HEALTH AUDIT{C.RESET}{' ' * 20}{B_DIM}│{C.RESET}")
    print(f"  {B_DIM}├{'─' * W_WIDTH}┤{C.RESET}")

    checks = [
        ("Backend Gateway (:8000)", "http://127.0.0.1:8000/api/health"),
        ("Neural Stack Readiness", "http://127.0.0.1:8000/api/ready"),
        ("Hardware Telemetry API", "http://127.0.0.1:8000/api/system/hardware"),
        ("System Configuration API", "http://127.0.0.1:8000/api/system/config"),
        ("Document Catalog API", "http://127.0.0.1:8000/api/documents"),
        ("Frontend Dev Server (:5173)", "http://127.0.0.1:5173"),
    ]

    for name, url in checks:
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RAISE-Doctor"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                status = resp.status
                latency = round((time.perf_counter() - t0) * 1000, 1)
                if 200 <= status < 400:
                    badge = f"{C.SUCCESS}\u2713 PASS{C.RESET} (HTTP {status} • {latency}ms)"
                else:
                    badge = f"{C.WARN}\u25b2 HTTP {status}{C.RESET} ({latency}ms)"
        except urllib.error.HTTPError as e:
            badge = f"{C.DANGER}\u2715 HTTP {e.code}{C.RESET} ({e.reason})"
        except Exception as e:
            badge = f"{C.DANGER}\u2715 UNREACHABLE{C.RESET} ({type(e).__name__})"

        print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {name:<30} {badge}")

    neo_ok = is_port_open(7687)
    neo_badge = f"{C.SUCCESS}\u2713 ONLINE{C.RESET} (Port 7687 responding)" if neo_ok else f"{C.WARN}\u25b2 STANDBY{C.RESET} (In-memory NetworkX active)"
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {'Neo4j Database (:7687)':<30} {neo_badge}")

    redis_ok = is_port_open(6379)
    redis_badge = f"{C.SUCCESS}\u2713 ONLINE{C.RESET} (Port 6379 responding)" if redis_ok else f"{C.MUTED}\u25cf STANDBY{C.RESET} (In-memory LRU active)"
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {'Redis Cache (:6379)':<30} {redis_badge}")

    pg_ok = is_port_open(5432)
    pg_badge = f"{C.SUCCESS}\u2713 ONLINE{C.RESET} (Port 5432 responding)" if pg_ok else f"{C.MUTED}\u25cf STANDBY{C.RESET} (SQLite local persistence)"
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} {'PostgreSQL Database (:5432)':<30} {pg_badge}")

    print(f"  {B_DIM}╰{'─' * W_WIDTH}╯{C.RESET}\n")


def print_help_cheatsheet() -> None:
    """Displays command reference cheatsheet in card style."""
    print(f"\n  {B_DIM}╭{'─' * W_WIDTH}╮{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.TITLE}📖 RAISE INTERACTIVE TERMINAL CHEATSHEET{C.RESET}{' ' * 35}{B_DIM}│{C.RESET}")
    print(f"  {B_DIM}├{'─' * W_WIDTH}┤{C.RESET}")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.ACCENT}<query>{C.RESET}           Run live question through full RAG research pipeline")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}status{C.RESET}            Display live hardware, database & model dashboard")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}doctor{C.RESET} / {C.NUM}diag{C.RESET}     Run forensic diagnostic check across all endpoints")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}docs{C.RESET} / {C.NUM}list{C.RESET}       List all registered PDFs with page/chunk counts")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}attach <N|name>{C.RESET}   Focus research scope strictly to document N or name")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}detach{C.RESET}            Reset research scope to ALL documents (library-wide)")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}logs backend{C.RESET}      View latest 30 lines of raw backend logs")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}logs frontend{C.RESET}     View latest 30 lines of raw frontend logs")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}model{C.RESET}             Display active LLM model, backend, and status")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}bench{C.RESET}             Run 3-query evaluation benchmark on active scope")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}├─{C.RESET} {C.NUM}clear{C.RESET} / {C.NUM}cls{C.RESET}       Clear console screen and redraw dashboard")
    print(f"  {B_DIM}│{C.RESET}  {B_DIM}╰─{C.RESET} {C.NUM}exit{C.RESET} / {C.NUM}quit{C.RESET}       Stop both backend and frontend servers and exit")
    print(f"  {B_DIM}╰{'─' * W_WIDTH}╯{C.RESET}\n")


# ==============================================================================
# Dual-Process Supervisor (Backend + Frontend)
# ==============================================================================

class DualProcessSupervisor:
    """
    Manages FastAPI Backend (:8000) and Vite Frontend (:5173) processes,
    streams unbuffered live logs with zero delay, and ensures clean termination.
    """

    def __init__(self, backend_dir: Path, frontend_dir: Path, python_exe: str, node_exe: Optional[str] = None):
        self.backend_dir = backend_dir
        self.frontend_dir = frontend_dir
        self.python_exe = python_exe

        if not node_exe or node_exe == "node":
            repo_root = backend_dir.parent if backend_dir.name == "backend" else backend_dir
            candidates = [
                repo_root / ".node" / "node-v22.14.0-win-x64" / "node.exe",
                frontend_dir / ".node" / "node-v22.14.0-win-x64" / "node.exe",
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "nodejs" / "node.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "node" / "node.exe",
            ]
            resolved_node = "node"
            for c in candidates:
                if c.exists():
                    resolved_node = str(c)
                    break
            self.node_exe = resolved_node
        else:
            self.node_exe = node_exe

        self.logs_dir = backend_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.backend_log_file = self.logs_dir / "backend.log"
        self.frontend_log_file = self.logs_dir / "frontend.log"

        self.backend_proc: Optional[subprocess.Popen] = None
        self.frontend_proc: Optional[subprocess.Popen] = None
        self.is_shutting_down = False

        self.backend_recent_logs: List[str] = []
        self.frontend_recent_logs: List[str] = []
        self.log_lock = threading.Lock()
        self._model_ready_announced = False
        self._last_progress_print = 0.0

    def _build_unbuffered_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["FORCE_COLOR"] = "1"
        return env

    def start_backend(self) -> bool:
        """Starts the FastAPI backend service with unbuffered pipes."""
        server_script = self.backend_dir / "server.py"
        cmd = [self.python_exe, "-u", str(server_script), "--no-tunnel"]

        try:
            self.backend_proc = subprocess.Popen(
                cmd,
                cwd=str(self.backend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=self._build_unbuffered_env(),
            )
            threading.Thread(target=self._stream_output, args=(self.backend_proc.stdout, "BACKEND", False), daemon=True).start()
            threading.Thread(target=self._stream_output, args=(self.backend_proc.stderr, "BACKEND-ERR", True), daemon=True).start()
            return True
        except Exception as e:
            print_supervisor_event(format_stream_row("SUPVR", f"Failed to start backend: {e}", "[ERR]", C.DANGER, C.DANGER))
            return False

    def start_frontend(self) -> bool:
        """Starts the React / Vite frontend service with unbuffered pipes."""
        vite_bin = self.frontend_dir / "node_modules" / "vite" / "bin" / "vite.js"
        if vite_bin.exists():
            cmd = [self.node_exe, str(vite_bin), "--clearScreen", "false"]
        else:
            cmd = ["cmd.exe", "/c", "npm", "run", "dev", "--", "--clearScreen", "false"]

        try:
            self.frontend_proc = subprocess.Popen(
                cmd,
                cwd=str(self.frontend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=self._build_unbuffered_env(),
            )
            threading.Thread(target=self._stream_output, args=(self.frontend_proc.stdout, "FRONTEND", False), daemon=True).start()
            threading.Thread(target=self._stream_output, args=(self.frontend_proc.stderr, "FRONTEND-ERR", True), daemon=True).start()
            return True
        except Exception as e:
            print_supervisor_event(format_stream_row("SUPVR", f"Failed to start frontend: {e}", "[ERR]", C.DANGER, C.DANGER))
            return False

    def _stream_output(self, stream, prefix: str, is_err: bool):
        """Streams process output in real time with zero artificial delay."""
        log_file = self.backend_log_file if "BACKEND" in prefix else self.frontend_log_file
        with open(log_file, "a", encoding="utf-8", errors="replace") as f_out:
            for line in iter(stream.readline, ""):
                if self.is_shutting_down:
                    break
                line = line.rstrip()
                if not line:
                    continue
                f_out.write(line + "\n")
                f_out.flush()

                with self.log_lock:
                    target_list = self.backend_recent_logs if "BACKEND" in prefix else self.frontend_recent_logs
                    target_list.append(line)
                    if len(target_list) > 150:
                        target_list.pop(0)

                clean_line = sanitize_text(line)

                # 1. Model loading / weights progress (silent during download, announce once ready)
                if any(kw in clean_line for kw in ("it/s", "%|", "Loading weights:", "Downloading")):
                    if ("100%|" in clean_line or "Loaded 20 prompts" in clean_line) and not self._model_ready_announced:
                        self._model_ready_announced = True
                        print_supervisor_event(format_stream_row("NEURAL", "Neural embedding weights initialized.", "\u2713", C.SUCCESS, C.SUCCESS))
                    continue

                # 2. High-value lifecycle & routing events
                if "Loading SentenceTransformer model" in clean_line:
                    model_id = clean_line.split("from")[-1].strip().rstrip(".")
                    print_supervisor_event(format_stream_row("NEURAL", f"Initializing SentenceTransformer ({model_id})...", "\u25cf", C.CYAN, C.WHITE))
                    continue

                if "Starting neural models pre-warming" in clean_line:
                    print_supervisor_event(format_stream_row("WARMUP", "Pre-warming neural inference stack (reranker, NLI)...", "\u25cf", C.CYAN, C.WHITE))
                    continue

                if "Neural models pre-warming completed successfully" in clean_line:
                    print_supervisor_event(format_stream_row("NEURAL", "All neural models warmed up and ready.", "\u2713", C.SUCCESS, C.SUCCESS))
                    continue

                if "Successfully mounted all core RAISE GraphRAG routes" in clean_line:
                    print_supervisor_event(format_stream_row("CORE", "All GraphRAG routers mounted successfully.", "\u2713", C.SUCCESS, C.WHITE))
                    continue

                if "[GRAPH-RAG]" in clean_line:
                    clean_rag = clean_line.split("[GRAPH-RAG]")[-1].strip()
                    print_supervisor_event(format_stream_row("GRAPHRAG", clean_rag, "\u25cf", C.CYAN, C.WHITE))
                    continue

                if "switched to" in clean_line and "Reason" in clean_line:
                    clean_fo = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[[A-Z]+\]\s+[^:]*:\s*', '', clean_line)
                    print_supervisor_event(format_stream_row("FAILOVER", clean_fo, "\u25b2", C.WARN, C.WARN))
                    continue

                if "[INFERENCE]" in clean_line or "Executing task" in clean_line:
                    clean_inf = clean_line.split("[INFERENCE]")[-1].replace("raise.infrastructure.providers.router:", "").strip()
                    clean_inf = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[[A-Z]+\]\s+[^:]*:\s*', '', clean_inf)
                    print_supervisor_event(format_stream_row("ROUTER", clean_inf, "\u25cf", C.ACCENT, C.WHITE))
                    continue

                if "Synthesis Success" in clean_line:
                    clean_syn = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[[A-Z]+\]\s+[^:]*:\s*', '', clean_line)
                    print_supervisor_event(format_stream_row("SYNTH", clean_syn, "\u2713", C.SUCCESS, C.SUCCESS))
                    continue

                if "POST /api/documents/upload" in clean_line:
                    print_supervisor_event(format_stream_row("INGEST", "Document upload received from UI Library.", "\u2713", C.SUCCESS, C.WHITE))
                    continue

                if "GET /api/pdf/" in clean_line and "200 OK" not in clean_line:
                    pdf_match = re.search(r'GET /api/pdf/([^ /]+)', clean_line)
                    pdf_name = urllib.parse.unquote(pdf_match.group(1)) if pdf_match else "PDF"
                    print_supervisor_event(format_stream_row("VIEWER", f"Streaming PDF: {pdf_name}", "\u25cf", C.MUTED, C.MUTED))
                    continue

                if "ready in" in clean_line or "Local:" in clean_line:
                    print_supervisor_event(format_stream_row("FRONTEND", "React / Vite UI ready on http://localhost:5173", "\u2713", C.SUCCESS, C.SUCCESS))
                    continue

                # 3. Filter only repetitive heartbeat / CORS noise so real events always show
                is_noisy_poll = any(ep in clean_line for ep in (
                    "HTTP Request: GET",
                    "HTTP Request: HEAD",
                    "httpx",
                    "httpcore",
                    "urllib3",
                    "OPTIONS /api/",
                    "GET /api/health",
                    "GET /api/system/hardware",
                    "GET /api/commands",
                    "GET /api/system/config",
                    "GET /favicon.ico",
                    "WebSocket /ws/traffic",
                    "connection open",
                    "connection closed",
                    "Started server process",
                    "Waiting for application startup",
                    "Application startup complete",
                    "Uvicorn running on",
                    "HEAD /api/pdf/",
                    "• Route      :",
                    "NumExpr detected",
                    "NumExpr defaulting",
                    "Registered slash command:",
                    "UserWarning: Duplicate Operation ID",
                    "Tunnel Mode: DISABLED",
                ))
                if is_noisy_poll:
                    continue

                # 4. Classify remaining Python / Uvicorn / Vite log lines
                log_match = re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[([A-Z]+)\]\s+([^:]*):\s+(.*)$', clean_line)
                if log_match:
                    log_level = log_match.group(1)
                    logger_tag = log_match.group(2).split(".")[-1].upper()[:8] or "BACKEND"
                    log_msg = log_match.group(3)
                else:
                    uvicorn_match = re.match(r'^(INFO|WARNING|WARN|ERROR|CRITICAL|DEBUG):\s+(.*)$', clean_line)
                    if uvicorn_match:
                        log_level = uvicorn_match.group(1).replace("WARN", "WARNING")
                        logger_tag = "FRONTEND" if "FRONTEND" in prefix else "BACKEND"
                        log_msg = uvicorn_match.group(2)
                    else:
                        warn_match = re.search(r'([A-Za-z]+Warning):\s*(.*)$', clean_line)
                        if warn_match:
                            log_level = "WARNING"
                            logger_tag = "WARN"
                            log_msg = f"{warn_match.group(1)}: {warn_match.group(2)}"
                        else:
                            is_real_err = is_err and any(w in clean_line.lower() for w in ("traceback", "exception", "critical", "syntaxerror", "importerror"))
                            log_level = "ERROR" if is_real_err else "INFO"
                            logger_tag = "FRONTEND" if "FRONTEND" in prefix else "BACKEND"
                            log_msg = clean_line.strip()

                is_error = (
                    log_level in ("ERROR", "CRITICAL")
                    or any(kw in log_msg.lower() for kw in ("traceback", "exception", "crash"))
                    or ("failed" in log_msg.lower() and not any(kw in log_msg for kw in ("0 failed", "failed: 0", "switched to")))
                ) and not any(kw in log_msg for kw in ("HTTP 200", "SUCCESS", "Synthesis Success"))

                is_warning = (
                    log_level == "WARNING"
                    or any(kw in log_msg.lower() for kw in ("warning", "warn", "auth_failed", "cooldown"))
                ) and not is_error

                if is_error:
                    print_supervisor_event(format_stream_row("ERROR", log_msg, "\u2715", C.DANGER, C.DANGER))
                elif is_warning:
                    print_supervisor_event(format_stream_row("WARNING", log_msg, "\u25b2", C.WARN, C.WARN))
                else:
                    if "HTTP/1.1\" 200 OK" not in log_msg:
                        print_supervisor_event(format_stream_row(logger_tag, log_msg, "\u25cf", C.CYAN, B_TXT))

    def wait_for_backend(self, timeout_sec: int = 300) -> bool:
        """Polls /api/health at high frequency (0.25s) for instant readiness detection."""
        timeout_env = os.getenv("RAISE_BACKEND_TIMEOUT")
        if timeout_env and timeout_env.isdigit():
            timeout_sec = int(timeout_env)
        t0 = time.time()
        last_heartbeat = t0
        while time.time() - t0 < timeout_sec:
            if self.backend_proc and self.backend_proc.poll() is not None:
                exit_code = self.backend_proc.poll()
                print_supervisor_event(format_stream_row("FATAL", f"Backend exited unexpectedly (code {exit_code})", "[ERR]", C.DANGER, C.DANGER))
                with self.log_lock:
                    for l in self.backend_recent_logs[-12:]:
                        print(f"    {C.MUTED}{l}{C.RESET}")
                return False
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"User-Agent": "RAISE-Supervisor"})
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass

            now = time.time()
            if now - last_heartbeat >= 8.0:
                elapsed = int(now - t0)
                print_supervisor_event(format_stream_row("SUPVR", f"Backend initializing neural models... ({elapsed}s / {timeout_sec}s)", "*", C.MUTED, C.MUTED))
                last_heartbeat = now

            time.sleep(0.25)

        print_supervisor_event(format_stream_row("FATAL", f"Backend timed out after {timeout_sec}s", "[ERR]", C.DANGER, C.DANGER))
        return False

    def wait_for_frontend(self, timeout_sec: int = 30) -> bool:
        """Polls Vite dev server at 0.2s intervals for instant boot handoff."""
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            if self.frontend_proc and self.frontend_proc.poll() is not None:
                return False
            if is_port_open(5173, timeout=0.4):
                return True
            time.sleep(0.2)
        return False

    def shutdown(self):
        """Terminates both services and ensures all child processes are killed."""
        self.is_shutting_down = True
        print(f"\n  {B_DIM}├─{C.RESET} {C.WARN}↻ Stopping services and releasing ports :8000 & :5173...{C.RESET}")

        for proc, _ in [(self.backend_proc, "Backend"), (self.frontend_proc, "Frontend")]:
            if proc and proc.poll() is None:
                try:
                    subprocess.run(f"taskkill /PID {proc.pid} /T /F", shell=True, capture_output=True, timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        free_port(8000)
        free_port(5173)
        print(f"  {B_DIM}╰─{C.RESET} {C.SUCCESS}[OK] All RAISE services stopped cleanly.{C.RESET}\n")


# ==============================================================================
# Live Research Query Execution
# ==============================================================================

def execute_terminal_query(query: str, focused_doc: Optional[str] = None) -> None:
    """Sends research query to running backend and renders grounded answer inside cards."""
    q_clean = query.strip()
    if not q_clean:
        return

    print(f"\n  {B_DIM}╭─{C.RESET} {C.CYAN}QUERY EXECUTION{C.RESET} {B_DIM}{'─' * (W_WIDTH - 18)}╮{C.RESET}")
    print(f"  {B_DIM}│{C.RESET} {C.ACCENT}>{C.RESET} {C.WHITE}{q_clean}{C.RESET}")
    print(f"  {B_DIM}╰{'─' * W_WIDTH}╯{C.RESET}")
    print_supervisor_event(format_stream_row("PIPELINE", "Executing multi-substrate GraphRAG + NLI verification...", "*", C.CYAN, C.MUTED))

    t0 = time.perf_counter()
    active_docs = [focused_doc] if focused_doc else None

    payload = {
        "query": q_clean,
        "mode": "expert",
        "stream": False,
        "active_docs": active_docs,
        "session_id": f"terminal-{int(time.time())}",
        "request_id": f"req-term-{int(time.time() * 1000)}",
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "RAISE-Terminal"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            latency = round((time.perf_counter() - t0), 2)
            ans = res.get("grounded_answer") or res.get("answer") or res.get("reply") or "No answer returned."

            header_label = f"GROUNDED SYNTHESIS ({latency}s)"
            pad_len = max(2, W_WIDTH - len(header_label) - 4)
            print(f"\n  {B_DIM}╭─{C.RESET} {C.SUCCESS}{header_label}{C.RESET} {B_DIM}{'─' * pad_len}╮{C.RESET}")
            for line in ans.splitlines():
                print(f"  {B_DIM}│{C.RESET} {C.WHITE}{line}{C.RESET}")

            citations = res.get("citations") or []
            if citations:
                print(f"  {B_DIM}├{'─' * W_WIDTH}┤{C.RESET}")
                print(f"  {B_DIM}│{C.RESET} {C.CYAN}CITATIONS{C.RESET}")
                for idx, c in enumerate(citations, 1):
                    branch = "╰─" if idx == len(citations) else "├─"
                    fn = c.get("pdf_filename") or "Document"
                    p = f" (p. {c.get('primary_page')})" if c.get("primary_page") else ""
                    print(f"  {B_DIM}│{C.RESET}  {B_DIM}{branch}{C.RESET} [{C.NUM}{c.get('citation_index', idx)}{C.RESET}] {C.WHITE}{fn}{p}{C.RESET}")

            claims = res.get("verified_claims") or []
            if claims:
                print(f"  {B_DIM}├{'─' * W_WIDTH}┤{C.RESET}")
                print(f"  {B_DIM}│{C.RESET} {C.WARN}VERIFIED CLAIMS (NLI AUDIT){C.RESET}")
                for idx, vc in enumerate(claims, 1):
                    branch = "╰─" if idx == len(claims) else "├─"
                    verdict = vc.get("status") or vc.get("verdict") or "VERIFIED"
                    v_badge = f"{C.SUCCESS}{verdict}{C.RESET}" if verdict in ("SUPPORTED", "VERIFIED") else f"{C.WARN}{verdict}{C.RESET}"
                    txt = vc.get("text") or vc.get("claim_text") or "Verified fact"
                    print(f"  {B_DIM}│{C.RESET}  {B_DIM}{branch}{C.RESET} [{v_badge}] {txt}")

            print(f"  {B_DIM}╰{'─' * W_WIDTH}╯{C.RESET}\n")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print_supervisor_event(format_stream_row("HTTP-ERR", f"Query failed (HTTP {e.code}): {err_msg}", "[ERR]", C.DANGER, C.DANGER))
    except Exception as e:
        print_supervisor_event(format_stream_row("ERROR", f"Query failed: {e}", "[ERR]", C.DANGER, C.DANGER))


# ==============================================================================
# Main Interactive Console REPL
# ==============================================================================

def main():
    """Main service supervisor loop."""
    repo_root = BASE_DIR.parent if BASE_DIR.name == "backend" else BASE_DIR
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"

    if "--doctor" in sys.argv or "--diag" in sys.argv:
        run_system_doctor()
        return

    if "--status" in sys.argv or "-s" in sys.argv:
        print_live_status_dashboard()
        return

    print_banner()

    free_port(8000)
    free_port(5173)

    python_exe = sys.executable
    supervisor = DualProcessSupervisor(
        backend_dir=backend_dir,
        frontend_dir=frontend_dir,
        python_exe=python_exe,
    )

    def _sig_handler(sig, frame):
        supervisor.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    try:
        signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass

    print(f"  {B_DIM}╭─{C.RESET} {C.CYAN}LIVE TELEMETRY STREAM (ZERO-DELAY UNBUFFERED I/O){C.RESET} {B_DIM}{'─' * 24}╮{C.RESET}")

    # 1. Launch Backend
    t_back = time.perf_counter()
    print_supervisor_event(format_stream_row("SUPVR", "Launching Backend Gateway on http://127.0.0.1:8000...", "*", C.CYAN, C.WHITE))
    if not supervisor.start_backend():
        print_supervisor_event(format_stream_row("FATAL", "Could not launch backend server.", "[ERR]", C.DANGER, C.DANGER))
        sys.exit(1)

    backend_timeout = int(os.getenv("RAISE_BACKEND_TIMEOUT", "300"))
    if not supervisor.wait_for_backend(timeout_sec=backend_timeout):
        print_supervisor_event(format_stream_row("FATAL", "Backend failed health check. Inspect backend.log.", "[ERR]", C.DANGER, C.DANGER))
        supervisor.shutdown()
        sys.exit(1)
    b_dur = round(time.perf_counter() - t_back, 1)
    print_supervisor_event(format_stream_row("SUPVR", f"Backend Gateway is LIVE on http://localhost:8000 ({b_dur}s)", "[OK]", C.SUCCESS, C.SUCCESS))

    # 2. Launch Frontend
    t_front = time.perf_counter()
    print_supervisor_event(format_stream_row("SUPVR", "Launching Frontend UI on http://localhost:5173...", "*", C.CYAN, C.WHITE))
    if not supervisor.start_frontend():
        print_supervisor_event(format_stream_row("FATAL", "Could not launch frontend server.", "[ERR]", C.DANGER, C.DANGER))
        supervisor.shutdown()
        sys.exit(1)

    if not supervisor.wait_for_frontend(timeout_sec=35):
        print_supervisor_event(format_stream_row("NOTICE", "Frontend still initializing in background...", "[!]", C.WARN, C.WARN))
    else:
        f_ms = int((time.perf_counter() - t_front) * 1000)
        print_supervisor_event(format_stream_row("SUPVR", f"Frontend UI is LIVE on http://localhost:5173 ({f_ms}ms)", "[OK]", C.SUCCESS, C.SUCCESS))

    print(f"  {B_DIM}╰{'─' * W_WIDTH}╯{C.RESET}\n")

    # Launch browser if not disabled
    no_browser = any(arg in sys.argv for arg in ("--no-browser", "-nb", "--nobrowser"))
    if not no_browser:
        target_url = "http://localhost:5173"
        try:
            import webbrowser
            webbrowser.open(target_url)
        except Exception:
            pass

    # Print Live Status Dashboard
    focused_doc: Optional[str] = None
    print_live_status_dashboard(focused_doc=focused_doc)

    global _active_repl_prompt, _active_prompt_header

    has_pt = False
    pt_session = None
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit.formatted_text import ANSI
        pt_session = PromptSession()
        has_pt = True
    except Exception:
        has_pt = False
        pt_session = None

    if has_pt and pt_session is not None:
        try:
            with patch_stdout(raw=True):
                while True:
                    try:
                        scope_badge = f"{focused_doc}" if focused_doc else "ALL DOCS"
                        header_str = f"  {B_DIM}╭─{C.RESET} [{C.TITLE}{scope_badge}{C.RESET}] {B_DIM}── Commands: status · doctor · docs · attach <N> · logs · exit ─╮{C.RESET}"
                        prompt_label = f"  {B_DIM}╰─{C.RESET} {C.ACCENT}RAISE{C.RESET} {B_DIM}>{C.RESET} "
                        full_prompt = f"{header_str}\n{prompt_label}"

                        user_input = pt_session.prompt(ANSI(full_prompt)).strip()
                        if not user_input:
                            continue
                        should_exit, focused_doc = dispatch_repl_command(user_input, focused_doc, supervisor)
                        if should_exit:
                            break
                    except KeyboardInterrupt:
                        break
                    except EOFError:
                        time.sleep(1.0)
                    except Exception as err:
                        print(f"{C.DANGER}[ERROR] Console error: {err}{C.RESET}")
                        time.sleep(0.5)
        except Exception:
            # Fallback to standard REPL if prompt_toolkit or patch_stdout encounters an issue
            has_pt = False

    if not has_pt:
        while True:
            try:
                scope_badge = f"{focused_doc}" if focused_doc else "ALL DOCS"
                _active_prompt_header = f"  {B_DIM}╭─{C.RESET} [{C.TITLE}{scope_badge}{C.RESET}] {B_DIM}── Commands: status · doctor · docs · attach <N> · logs · exit ─╮{C.RESET}"
                _active_repl_prompt = f"  {B_DIM}╰─{C.RESET} {C.ACCENT}RAISE{C.RESET} {B_DIM}>{C.RESET} "

                try:
                    print(_active_prompt_header)
                    user_input = input(_active_repl_prompt).strip()
                finally:
                    _active_repl_prompt = None
                    _active_prompt_header = None

                if not user_input:
                    continue

                should_exit, focused_doc = dispatch_repl_command(user_input, focused_doc, supervisor)
                if should_exit:
                    break
            except KeyboardInterrupt:
                break
            except EOFError:
                # Keep background server processes running in headless or piped modes
                time.sleep(1.0)
            except Exception as err:
                print(f"{C.DANGER}[ERROR] Console error: {err}{C.RESET}")
                time.sleep(0.5)

    supervisor.shutdown()


def dispatch_repl_command(
    user_input: str,
    focused_doc: Optional[str],
    supervisor: DualProcessSupervisor,
) -> Tuple[bool, Optional[str]]:
    """
    Dispatches interactive REPL commands.
    Returns (should_exit, updated_focused_doc).
    """
    cmd_lower = user_input.lower().strip()
    if cmd_lower in ("exit", "quit", "q", ":q"):
        return True, focused_doc
    elif cmd_lower in ("help", "?", "commands"):
        print_help_cheatsheet()
    elif cmd_lower in ("status", "health", "info"):
        print_live_status_dashboard(focused_doc=focused_doc)
    elif cmd_lower in ("doctor", "diag", "test"):
        run_system_doctor()
    elif cmd_lower in ("clear", "cls"):
        os.system("cls" if os.name == "nt" else "clear")
        print_banner()
        print_live_status_dashboard(focused_doc=focused_doc)
    elif cmd_lower in ("docs", "list", "documents"):
        docs = get_active_documents_list()
        print(f"\n{C.TITLE}📚 Active Ingested Document Catalog ({len(docs)} files):{C.RESET}")
        for idx, d in enumerate(docs, 1):
            fn = d.get("filename", "")
            pgs = d.get("pages", 0)
            chks = d.get("chunks_count", 0)
            sz = f"{d.get('size_mb', 0):.1f}MB"
            foc_marker = f" {C.SUCCESS}◄ ACTIVE TARGET{C.RESET}" if focused_doc and focused_doc.lower() in fn.lower() else ""
            print(f"  [{C.NUM}{idx}{C.RESET}] {C.WHITE}{fn:<40}{C.RESET} | {pgs:>3}p | {chks:>4} chks | {sz:>7}{foc_marker}")
        print("")
    elif cmd_lower.startswith("attach "):
        target = user_input[7:].strip()
        docs = get_active_documents_list()
        matched = None
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(docs):
                matched = docs[idx].get("filename")
        else:
            for d in docs:
                if target.lower() in d.get("filename", "").lower():
                    matched = d.get("filename")
                    break
        if matched:
            focused_doc = matched
            print(f"{C.SUCCESS}🎯 Attached focus target: '{focused_doc}'{C.RESET}\n")
        else:
            print(f"{C.WARN}⚠️  Document matching '{target}' not found.{C.RESET}\n")
    elif cmd_lower in ("detach", "attach all", "clear focus"):
        focused_doc = None
        print(f"{C.SUCCESS}🎯 Research scope reset to ALL DOCUMENTS.{C.RESET}\n")
    elif cmd_lower == "logs backend":
        print(f"\n{C.TITLE}📜 Latest Backend Logs (last 30 lines):{C.RESET}")
        with supervisor.log_lock:
            for l in supervisor.backend_recent_logs[-30:]:
                print(f"  {l}")
        print("")
    elif cmd_lower == "logs frontend":
        print(f"\n{C.TITLE}📜 Latest Frontend Logs (last 30 lines):{C.RESET}")
        with supervisor.log_lock:
            for l in supervisor.frontend_recent_logs[-30:]:
                print(f"  {l}")
        print("")
    elif cmd_lower == "model":
        synth = get_synthesizer_status()
        print(f"\n{C.TITLE}🤖 Active Model Configuration:{C.RESET}")
        print(f"  • Provider : {synth.get('provider', 'unknown')}")
        print(f"  • Model    : {synth.get('model', 'unknown')}")
        print(f"  • Status   : {synth.get('display_string')}\n")
    elif cmd_lower == "bench":
        print(f"\n{C.TITLE}Running Benchmark Verification...{C.RESET}")
        print(f"  Execute the full scientific evaluation harness via:")
        print(f"  {C.CYAN}python evaluation/run_ragas_benchmarks.py{C.RESET}\n")
    elif cmd_lower.startswith("substrate ") or cmd_lower.startswith("profile "):
        parts = cmd_lower.split(None, 1)
        if len(parts) > 1 and parts[1].strip() in ("fast", "docker", "cloud"):
            target_mode = parts[1].strip()
            os.environ["RAISE_SUBSTRATE_MODE"] = target_mode
            os.environ["USE_FAKEREDIS"] = "true" if target_mode == "fast" else "false"
            print_supervisor_event(
                format_stream_row("SUBSTRATE", f"Switched runtime profile to {target_mode.upper()} MODE", "*", C.SUCCESS, C.SUCCESS)
            )
            _render_status_dashboard(focused_doc=focused_doc)
        else:
            print_supervisor_event(
                format_stream_row("SUBSTRATE", "Usage: 'substrate fast' | 'substrate docker' | 'substrate cloud'", "[WARN]", C.WARN, C.WARN)
            )
    else:
        execute_terminal_query(user_input, focused_doc=focused_doc)

    return False, focused_doc


if __name__ == "__main__":
    main()
