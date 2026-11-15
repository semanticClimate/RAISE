"""
RAISE — Dual Workstation Supervisor & Interactive Terminal Console
===================================================================
Modular service manager and developer observability console:
1. Orchestrates FastAPI Backend (:8000) and React/Vite Frontend (:5173).
2. Live streaming log telemetry with semantic color demarcation.
3. Non-blocking interactive terminal REPL with direct keyboard input.
4. Real-time diagnostics, hardware telemetry, and model status (from dev_main.py).
5. Robust signal handling and automatic port cleanup on shutdown.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 unbuffered write-through console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", write_through=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", write_through=True)

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Enable ANSI colors
try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

from src.cli.renderer import C
from src.cli.document_manager import get_active_documents_list
from src.cli.system_launcher import get_synthesizer_status
from src.core.config import models

logger = logging.getLogger("RAISE_ServiceRunner")

# High-contrast TrueColor stream tags and box styling constants
DIM = "\033[38;5;240m"
TAG_READY = "\033[38;5;48m● READY\033[0m"
TAG_FAST = "\033[38;5;39m⚡ FAST-PATH\033[0m"
TAG_SYNC = "\033[38;5;220m↻ SYNC\033[0m"
TAG_NEURAL = "\033[38;5;141m◆ NEURAL\033[0m"
TAG_INGEST = "\033[38;5;214m╰─ INGEST\033[0m"
TAG_RAG = "\033[38;5;45m🔍 RAG\033[0m"
TAG_FAILOVER = "\033[38;5;196m✕ FAILOVER\033[0m"
TAG_WARN = "\033[38;5;220m⚠️  WARN\033[0m"


def format_stream_row(tag: str, text: str) -> str:
    """Formats an operational event row with dim brackets and high-contrast badge."""
    return f"{DIM}[{C.RESET}{tag}{DIM}]{C.RESET} {text}"


# Global console prompt synchronization lock
_console_lock = threading.Lock()
_active_repl_prompt: Optional[str] = None


def print_supervisor_event(text: str) -> None:
    """
    Prints a real-time event to the interactive terminal without mangling or
    overwriting the user's active keyboard prompt line.
    """
    with _console_lock:
        global _active_repl_prompt
        if _active_repl_prompt:
            # Erase active prompt line via ANSI sequence, print event, then redraw prompt
            sys.stdout.write(f"\r\033[K{text}\n{_active_repl_prompt}")
            sys.stdout.flush()
        else:
            print(text)
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
    """Renders the top-level RAISE workstation banner with clean rounded box geometry."""
    print("\n" + DIM + "╭─" + "─" * 74 + "╮" + C.RESET)
    print(f"{DIM}│{C.RESET}  {C.TITLE}🚀 RAISE ACADEMIC GRAPHRAG STUDIO{C.RESET} — {C.CYAN}MONOREPO WORKSTATION{C.RESET}{' ' * 16}{DIM}│{C.RESET}")
    print(f"{DIM}│{C.RESET}  {C.MUTED}Backend API : http://localhost:8000   | Swagger Docs: http://localhost:8000/docs{C.RESET}{DIM}│{C.RESET}")
    print(f"{DIM}│{C.RESET}  {C.MUTED}Frontend UI : http://localhost:5173   | Architecture: Hybrid GraphRAG + NLI{C.RESET}{DIM}│{C.RESET}")
    print(DIM + "╰─" + "─" * 74 + "╯" + C.RESET + "\n")


def _render_status_dashboard(focused_doc: Optional[str] = None) -> None:
    """Renders real-time diagnostic dashboard modeled from dev_main.py."""
    print(DIM + "╭─" + "─" * 74 + "╮" + C.RESET)
    print(f"{DIM}│{C.RESET} {C.TITLE}🩺  RAISE WORKSTATION HEALTH & SUBSYSTEM DIAGNOSTICS{C.RESET}{' ' * 23}{DIM}│{C.RESET}")

    # 1. Hardware Summary (with instantaneous local fallback)
    hw = fetch_json_endpoint("http://127.0.0.1:8000/api/system/hardware", timeout=1.5)
    if hw:
        cuda_active = bool(hw.get("has_metal_or_cuda") or hw.get("cuda_available") or hw.get("gpu_detected"))
        vram = hw.get("vram_gb") or hw.get("gpu_vram_gb", 0)
        raw_gpu = hw.get("gpu")
        gpu_name = hw.get("gpu_name") or (raw_gpu.get("details") if isinstance(raw_gpu, dict) else "None")
        gpu_str = f"{gpu_name} ({float(vram):.1f}GB VRAM)" if (cuda_active and gpu_name and gpu_name != "None") else "CPU Only (CUDA Inactive)"
        avail_ram = hw.get("free_ram_gb") or hw.get("ram_available_gb") or hw.get("available_ram_gb", 0)
        tot_ram = hw.get("total_ram_gb") or hw.get("ram_total_gb", 0)
        ram_str = f"{float(avail_ram):.1f} GB avail / {float(tot_ram):.1f} GB total"
        cpu_cnt = hw.get("cpu_cores") or hw.get("cpu_count", 0)
        hw_line = f"GPU: {gpu_str} | RAM: {ram_str} ({cpu_cnt} Cores)"
    else:
        try:
            import psutil
            ram = psutil.virtual_memory()
            ram_str = f"{ram.available / (1024**3):.1f} GB avail / {ram.total / (1024**3):.1f} GB total"
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
            hw_line = f"GPU: {gpu_str} | RAM: {ram_str} ({cpu_cnt} Cores)"
        except Exception:
            hw_line = "Hardware detection ready"
    print(f"{DIM}│{C.RESET} {C.MUTED}Hardware: {hw_line}{C.RESET}")
    print(DIM + "├─" + "─" * 74 + "┤" + C.RESET)

    # 2. Subsystems
    # Backend Config & Provenance Models
    cfg = fetch_json_endpoint("http://127.0.0.1:8000/api/system/config", timeout=1.5) or {}
    prov = fetch_json_endpoint("http://127.0.0.1:8000/api/system/provenance", timeout=1.5) or {}
    synth = get_synthesizer_status()

    # ChromaDB Count (Lightweight PersistentClient check without loading PyTorch weights in supervisor)
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

    # Substrate Network Probes
    neo4j_online = is_port_open(7687)
    neo4j_str = f"{C.SUCCESS}CONNECTED (bolt://localhost:7687){C.RESET}" if neo4j_online else f"{C.WARN}STANDBY (In-memory NetworkX active){C.RESET}"
    
    redis_online = is_port_open(6379)
    redis_str = f"{C.SUCCESS}CONNECTED (localhost:6379){C.RESET}" if redis_online else f"{C.MUTED}STANDBY (In-memory LRU active){C.RESET}"
    
    pg_online = is_port_open(5432)
    pg_str = f"{C.SUCCESS}CONNECTED (localhost:5432){C.RESET}" if pg_online else f"{C.MUTED}STANDBY (SQLite local persistence){C.RESET}"

    chroma_str = f"{C.SUCCESS}ACTIVE ({chroma_count} chunks | {chroma_model} 768-dim){C.RESET}" if chroma_online else f"{C.WARN}EMPTY / OFFLINE{C.RESET}"
    synth_str = synth.get("display_string", f"{C.SUCCESS}ACTIVE{C.RESET}")

    encoder_name = prov.get("encoder_model") or cfg.get("embedding_model") or chroma_model
    reranker_name = prov.get("reranker_model") or cfg.get("reranker_model") or models.RERANKER_MODEL_NAME
    nli_name = prov.get("nli_verifier_model") or cfg.get("nli_verifier_model") or models.NLI_MODEL_NAME

    print(f"{DIM}│{C.RESET} {C.SECTION}CONNECTION & NETWORK TOPOLOGY:{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Backend API Gateway       : {C.WHITE}http://localhost:8000{C.RESET} | Swagger: {C.CYAN}/docs{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Frontend Workstation UI   : {C.WHITE}http://localhost:5173{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Live Telemetry Stream     : {C.WHITE}ws://localhost:8000/ws/traffic{C.RESET}")
    print(f"{DIM}│{C.RESET}")
    print(f"{DIM}│{C.RESET} {C.SECTION}STORAGE & DATABASE SUBSTRATES:{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Vector Store (ChromaDB)   : {chroma_str}")
    print(f"{DIM}│{C.RESET}   • Knowledge Graph (Neo4j)   : {neo4j_str}")
    print(f"{DIM}│{C.RESET}   • Semantic Cache (Redis)    : {redis_str}")
    print(f"{DIM}│{C.RESET}   • Relational DB (Postgres)  : {pg_str}")
    print(f"{DIM}│{C.RESET}")
    print(f"{DIM}│{C.RESET} {C.SECTION}AI NEURAL MODEL PIPELINE:{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Synthesis LLM Engine      : {synth_str}")
    print(f"{DIM}│{C.RESET}   • Dense Embedding Encoder   : {C.WHITE}{encoder_name}{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Cross-Attention Reranker  : {C.WHITE}{reranker_name}{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Claim Entailment Verifier : {C.WHITE}{nli_name}{C.RESET}")

    # Active Documents
    docs = get_active_documents_list()
    print(f"{DIM}│{C.RESET}")
    print(f"{DIM}│{C.RESET} {C.SECTION}REGISTERED DOCUMENT LIBRARY ({len(docs)} documents):{C.RESET}")
    if docs:
        for idx, d in enumerate(docs[:8], 1):
            fn = d.get("filename", "document.pdf")
            short_fn = fn if len(fn) <= 38 else fn[:35] + "..."
            pgs = d.get("pages", 0)
            chks = d.get("chunks_count", 0)
            sz = f"{d.get('size_mb', 0):.1f}MB"
            print(f"{DIM}│{C.RESET}   [{C.NUM}{idx}{C.RESET}] {C.WHITE}{short_fn:<38}{C.RESET} {C.NUM}{pgs:>3}p{C.RESET} | {C.NUM}{chks:>3} chks{C.RESET} | {sz:>7}")
        if len(docs) > 8:
            print(f"{DIM}│{C.RESET}   ... and {len(docs) - 8} more documents (use 'docs' to list all)")
    else:
        print(f"{DIM}│{C.RESET}   {C.WARN}⚠️  No documents in catalog. Upload PDFs via Web UI or 'upload <path>'{C.RESET}")

    scope_name = f"'{focused_doc}' (Single Document Target)" if focused_doc else "ALL REGISTERED DOCUMENTS (Multi-Hop Graph Scope)"
    print(f"{DIM}│{C.RESET}")
    print(f"{DIM}│{C.RESET} {C.SECTION}INTERACTIVE CONSOLE STATE:{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Active Research Scope     : {C.ACCENT}{scope_name}{C.RESET}")
    print(f"{DIM}│{C.RESET}   • Web UI Link               : {C.CYAN}http://localhost:5173{C.RESET}")
    print(DIM + "╰─" + "─" * 74 + "╯" + C.RESET + "\n")


def print_live_status_dashboard(focused_doc: Optional[str] = None) -> None:
    """Thread-safe entrypoint ensuring the ASCII dashboard is never mangled by background events."""
    with _console_lock:
        _render_status_dashboard(focused_doc)


def run_system_doctor() -> None:
    """Executes end-to-end diagnostic probes on all endpoints and services."""
    print("\n" + C.BANNER + "═" * 76 + C.RESET)
    print(f" {C.TITLE}🩺 RAISE SYSTEM DOCTOR — FORENSIC ENDPOINT HEALTH AUDIT{C.RESET}")
    print(C.BANNER + "═" * 76 + C.RESET)

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
                    badge = f"{C.SUCCESS}PASS (HTTP {status} | {latency}ms){C.RESET}"
                else:
                    badge = f"{C.WARN}HTTP {status} ({latency}ms){C.RESET}"
        except urllib.error.HTTPError as e:
            badge = f"{C.DANGER}HTTP {e.code} ({e.reason}){C.RESET}"
        except Exception as e:
            badge = f"{C.DANGER}UNREACHABLE ({type(e).__name__}){C.RESET}"

        print(f"  • {name:<32} : {badge}")

    # Storage substrates probe
    neo_ok = is_port_open(7687)
    neo_badge = f"{C.SUCCESS}ONLINE (Port 7687 responding){C.RESET}" if neo_ok else f"{C.WARN}STANDBY (In-memory NetworkX active){C.RESET}"
    print(f"  • {'Neo4j Database (:7687)':<32} : {neo_badge}")

    redis_ok = is_port_open(6379)
    redis_badge = f"{C.SUCCESS}ONLINE (Port 6379 responding){C.RESET}" if redis_ok else f"{C.MUTED}STANDBY (In-memory LRU active){C.RESET}"
    print(f"  • {'Redis Cache (:6379)':<32} : {redis_badge}")

    pg_ok = is_port_open(5432)
    pg_badge = f"{C.SUCCESS}ONLINE (Port 5432 responding){C.RESET}" if pg_ok else f"{C.MUTED}STANDBY (SQLite local persistence active){C.RESET}"
    print(f"  • {'PostgreSQL Database (:5432)':<32} : {pg_badge}")

    print(C.BANNER + "═" * 76 + C.RESET + "\n")


def print_help_cheatsheet() -> None:
    """Displays command reference cheatsheet."""
    print("\n" + C.BANNER + "═" * 76 + C.RESET)
    print(f" {C.TITLE}📖 RAISE INTERACTIVE TERMINAL CHEATSHEET{C.RESET}")
    print(C.BANNER + "═" * 76 + C.RESET)
    print(f"  • {C.ACCENT}<query>{C.RESET}           : Run live question through full RAG research pipeline")
    print(f"  • {C.NUM}status{C.RESET}            : Display full live hardware, database & model dashboard")
    print(f"  • {C.NUM}doctor{C.RESET} / {C.NUM}diag{C.RESET}     : Run forensic diagnostic check across all endpoints & ports")
    print(f"  • {C.NUM}docs{C.RESET} / {C.NUM}list{C.RESET}        : List all registered PDFs in library with page/chunk counts")
    print(f"  • {C.NUM}attach <N|name>{C.RESET}  : Focus research scope strictly to document N or filename")
    print(f"  • {C.NUM}detach{C.RESET}           : Reset research scope to ALL documents (library-wide)")
    print(f"  • {C.NUM}logs backend{C.RESET}     : View latest 30 lines of backend logs")
    print(f"  • {C.NUM}logs frontend{C.RESET}    : View latest 30 lines of frontend logs")
    print(f"  • {C.NUM}model{C.RESET}            : Display active LLM model, backend, and health latency")
    print(f"  • {C.NUM}bench{C.RESET}            : Run a quick 3-query evaluation benchmark on active document")
    print(f"  • {C.NUM}clear{C.RESET} / {C.NUM}cls{C.RESET}       : Clear console screen and redraw dashboard")
    print(f"  • {C.NUM}help{C.RESET}             : Show this cheat sheet")
    print(f"  • {C.NUM}exit{C.RESET} / {C.NUM}quit{C.RESET}       : Stop both backend and frontend servers and exit")
    print(C.BANNER + "═" * 76 + C.RESET + "\n")


# ==============================================================================
# Dual-Process Supervisor (Backend + Frontend)
# ==============================================================================

class DualProcessSupervisor:
    """
    Manages FastAPI Backend (:8000) and Vite Frontend (:5173) processes,
    captures and formats logs with color tags, and ensures clean termination.
    """

    def __init__(self, backend_dir: Path, frontend_dir: Path, python_exe: str, node_exe: Optional[str] = None):
        self.backend_dir = backend_dir
        self.frontend_dir = frontend_dir
        self.python_exe = python_exe

        # Auto-discover Node.js runtime if not explicitly passed
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

    def start_backend(self) -> bool:
        """Starts the FastAPI backend service with unbuffered I/O."""
        server_script = self.backend_dir / "server.py"
        cmd = [self.python_exe, "-u", str(server_script), "--no-tunnel"]
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"
        env["TERM"] = "xterm-256color"

        try:
            self.backend_proc = subprocess.Popen(
                cmd,
                cwd=str(self.backend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            # Start background reader threads
            threading.Thread(target=self._stream_output, args=(self.backend_proc.stdout, "BACKEND", False), daemon=True).start()
            threading.Thread(target=self._stream_output, args=(self.backend_proc.stderr, "BACKEND-ERR", True), daemon=True).start()
            return True
        except Exception as e:
            print(f"{C.DANGER}[ERROR] Failed to start backend: {e}{C.RESET}")
            return False

    def start_frontend(self) -> bool:
        """Starts the React / Vite frontend service with unbuffered I/O."""
        vite_bin = self.frontend_dir / "node_modules" / "vite" / "bin" / "vite.js"
        if vite_bin.exists():
            cmd = [self.node_exe, str(vite_bin), "--clearScreen", "false"]
        else:
            cmd = ["cmd.exe", "/c", "npm", "run", "dev", "--", "--clearScreen", "false"]

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TERM"] = "xterm-256color"

        try:
            self.frontend_proc = subprocess.Popen(
                cmd,
                cwd=str(self.frontend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            # Start background reader threads
            threading.Thread(target=self._stream_output, args=(self.frontend_proc.stdout, "FRONTEND", False), daemon=True).start()
            threading.Thread(target=self._stream_output, args=(self.frontend_proc.stderr, "FRONTEND-ERR", True), daemon=True).start()
            return True
        except Exception as e:
            print(f"{C.DANGER}[ERROR] Failed to start frontend: {e}{C.RESET}")
            return False

    def _stream_output(self, stream, prefix: str, is_err: bool):
        """Reads process output line by line, formats real-time operational telemetry, and preserves clean console state."""
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
                    if len(target_list) > 100:
                        target_list.pop(0)

                clean_line = sanitize_text(line)

                # 1. Capture model loading / weights progress (throttled at 0.25s for instantaneous telemetry):
                if any(kw in clean_line for kw in ("it/s", "%|", "Loading weights:", "Downloading")):
                    if ("100%|" in clean_line or "Loaded 20 prompts" in clean_line) and not self._model_ready_announced:
                        self._model_ready_announced = True
                        print_supervisor_event(format_stream_row(TAG_READY, "Neural embedding weights initialized successfully."))
                    else:
                        now_ts = time.time()
                        if now_ts - self._last_progress_print >= 0.25:
                            self._last_progress_print = now_ts
                            short_prog = clean_line.strip()
                            if len(short_prog) > 85:
                                short_prog = short_prog[:82] + "..."
                            print_supervisor_event(format_stream_row(TAG_NEURAL, short_prog))
                    continue

                # 2. Check for high-value lifecycle & routing events first
                if "Loading SentenceTransformer model" in clean_line:
                    model_id = clean_line.split("from")[-1].strip().rstrip(".")
                    print_supervisor_event(format_stream_row(TAG_NEURAL, f"Initializing SentenceTransformer ({model_id})..."))
                    continue

                if "Starting neural models pre-warming" in clean_line:
                    print_supervisor_event(format_stream_row(TAG_FAST, "Pre-warming neural inference stack (reranker, NLI)..."))
                    continue

                if "Neural models pre-warming completed successfully" in clean_line:
                    print_supervisor_event(format_stream_row(TAG_READY, "All neural models warmed up and ready."))
                    continue

                if "Successfully mounted all core RAISE GraphRAG routes" in clean_line:
                    print_supervisor_event(format_stream_row(TAG_READY, "All GraphRAG routers mounted successfully."))
                    continue

                if "[GRAPH-RAG]" in clean_line:
                    clean_rag = clean_line.split("[GRAPH-RAG]")[-1].strip()
                    print_supervisor_event(format_stream_row(TAG_RAG, clean_rag))
                    continue

                if "switched to" in clean_line and "Reason" in clean_line:
                    clean_fo = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[[A-Z]+\]\s+[^:]*:\s*', '', clean_line)
                    print_supervisor_event(format_stream_row(TAG_FAILOVER, clean_fo))
                    continue

                if "Permanently disabled" in clean_line:
                    clean_dis = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[[A-Z]+\]\s+[^:]*:\s*', '', clean_line)
                    print_supervisor_event(format_stream_row(TAG_WARN, clean_dis))
                    continue

                if "[INFERENCE]" in clean_line or "Executing task" in clean_line:
                    clean_inf = clean_line.split("[INFERENCE]")[-1].replace("raise.infrastructure.providers.router:", "").strip()
                    clean_inf = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[[A-Z]+\]\s+[^:]*:\s*', '', clean_inf)
                    print_supervisor_event(format_stream_row(TAG_RAG, clean_inf))
                    continue

                if "Synthesis Success" in clean_line:
                    clean_syn = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[[A-Z]+\]\s+[^:]*:\s*', '', clean_line)
                    print_supervisor_event(format_stream_row(TAG_FAST, f"Synthesis Success: {clean_syn}"))
                    continue

                if "POST /api/documents/upload" in clean_line:
                    print_supervisor_event(format_stream_row(TAG_INGEST, "Document upload received from UI Library."))
                    continue

                if "GET /api/pdf/" in clean_line and "200 OK" not in clean_line:
                    pdf_match = re.search(r'GET /api/pdf/([^ /]+)', clean_line)
                    pdf_name = urllib.parse.unquote(pdf_match.group(1)) if pdf_match else "PDF"
                    print_supervisor_event(format_stream_row(TAG_SYNC, f"Streaming PDF: {pdf_name}"))
                    continue

                if "ready in" in clean_line or "Local:" in clean_line:
                    print_supervisor_event(format_stream_row(TAG_READY, "React / Vite workstation ready on http://localhost:5173"))
                    continue

                # 3. Suppress high-frequency background polling endpoints, raw HTTP access logs & internal noise
                is_noisy_poll = any(ep in clean_line for ep in (
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
                    "HTTP/1.1\" 200 OK",
                    "HEAD /api/pdf/",
                    "• Route      :",
                    "NumExpr detected",
                    "NumExpr defaulting",
                    "Connected to Persistent Local SQLite Database",
                    "Connected to Local Redis",
                    "Registered slash command:",
                    "Mounted production frontend from",
                    "UserWarning: Duplicate Operation ID",
                    "Tunnel Mode: DISABLED",
                ))
                if is_noisy_poll:
                    continue

                # 4. Clean and classify Python / Uvicorn logger lines
                log_match = re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+\[([A-Z]+)\]\s+[^:]*:\s+(.*)$', clean_line)
                if log_match:
                    log_level = log_match.group(1)
                    log_msg = log_match.group(2)
                else:
                    uvicorn_match = re.match(r'^(INFO|WARNING|WARN|ERROR|CRITICAL|DEBUG):\s+(.*)$', clean_line)
                    if uvicorn_match:
                        log_level = uvicorn_match.group(1).replace("WARN", "WARNING")
                        log_msg = uvicorn_match.group(2)
                    else:
                        warn_match = re.search(r'([A-Za-z]+Warning):\s*(.*)$', clean_line)
                        if warn_match:
                            log_level = "WARNING"
                            log_msg = f"{warn_match.group(1)}: {warn_match.group(2)}"
                        else:
                            is_real_err = is_err and any(w in clean_line.lower() for w in ("traceback", "exception", "critical", "syntaxerror", "importerror"))
                            log_level = "ERROR" if is_real_err else "INFO"
                            log_msg = clean_line

                # 5. Critical Warnings & Errors (Never Silenced, High Visibility)
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
                    print_supervisor_event(f"{C.DANGER}❌ [ERROR] {log_msg}{C.RESET}")
                    continue

                if is_warning:
                    print_supervisor_event(f"{C.WARN}⚠️  [WARNING] {log_msg}{C.RESET}")
                    continue

    def wait_for_backend(self, timeout_sec: int = 180) -> bool:
        """Polls /api/health until the backend gateway is alive, surfacing real-time telemetry."""
        t0 = time.time()
        last_heartbeat = t0
        while time.time() - t0 < timeout_sec:
            if self.backend_proc and self.backend_proc.poll() is not None:
                exit_code = self.backend_proc.poll()
                print(f"\n{C.DANGER}[FATAL] Backend process exited unexpectedly with code {exit_code}.{C.RESET}")
                with self.log_lock:
                    if self.backend_recent_logs:
                        print(f"{C.WARN}--- Recent backend log output ---{C.RESET}")
                        for l in self.backend_recent_logs[-12:]:
                            print(f"{C.MUTED}{l}{C.RESET}")
                return False
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"User-Agent": "RAISE-Supervisor"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass

            now = time.time()
            if now - last_heartbeat >= 10.0:
                elapsed = int(now - t0)
                print(f"{C.MUTED}[RAISE] Backend initializing neural models & services... ({elapsed}s elapsed / {timeout_sec}s timeout){C.RESET}")
                last_heartbeat = now

            time.sleep(0.8)

        print(f"\n{C.DANGER}[FATAL] Backend startup timed out after {timeout_sec}s without reporting health.{C.RESET}")
        with self.log_lock:
            if self.backend_recent_logs:
                print(f"{C.WARN}--- Recent backend log output ---{C.RESET}")
                for l in self.backend_recent_logs[-12:]:
                    print(f"{C.MUTED}{l}{C.RESET}")
        return False

    def wait_for_frontend(self, timeout_sec: int = 30) -> bool:
        """Polls Vite dev server until HTTP 200/300 is returned."""
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            if self.frontend_proc and self.frontend_proc.poll() is not None:
                return False
            if is_port_open(5173, timeout=0.8):
                return True
            time.sleep(0.8)
        return False

    def shutdown(self):
        """Terminates both services and ensures all child processes are killed."""
        self.is_shutting_down = True
        print(f"\n{C.WARN}[RAISE] Stopping services and releasing ports...{C.RESET}")

        for proc, name in [(self.backend_proc, "Backend"), (self.frontend_proc, "Frontend")]:
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
        print(f"{C.SUCCESS}[RAISE] All services stopped cleanly. Goodbye!{C.RESET}\n")


# ==============================================================================
# Live Research Query Execution
# ==============================================================================

def execute_terminal_query(query: str, focused_doc: Optional[str] = None) -> None:
    """Sends research query to running backend and renders formatted grounded answer."""
    q_clean = query.strip()
    if not q_clean:
        return

    print(f"\n{C.CYAN}[QUERY]{C.RESET} {q_clean}")
    print(f"{C.MUTED}[THINKING] Executing multi-substrate research pipeline...{C.RESET}")
    
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

            print(f"\n{C.SUCCESS}[ANSWER] ({latency}s){C.RESET}")
            print(f"{C.WHITE}{ans}{C.RESET}")

            citations = res.get("citations") or []
            if citations:
                print(f"\n{C.CYAN}[CITATIONS]{C.RESET}")
                for c in citations:
                    fn = c.get("pdf_filename") or "Document"
                    p = f" (p. {c.get('primary_page')})" if c.get("primary_page") else ""
                    print(f"  • [{c.get('citation_index', '*')}] {C.WHITE}{fn}{p}{C.RESET}")

            claims = res.get("verified_claims") or []
            if claims:
                print(f"\n{C.WARN}[VERIFIED CLAIMS]{C.RESET}")
                for vc in claims:
                    verdict = vc.get("status") or vc.get("verdict") or "VERIFIED"
                    v_badge = f"{C.SUCCESS}{verdict}{C.RESET}" if verdict in ("SUPPORTED", "VERIFIED") else f"{C.WARN}{verdict}{C.RESET}"
                    txt = vc.get("text") or vc.get("claim_text") or "Verified fact"
                    print(f"  • {txt} [{v_badge}]")

            print("")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print(f"\n{C.DANGER}[ERROR] Query failed with HTTP {e.code}: {err_msg}{C.RESET}\n")
    except Exception as e:
        print(f"\n{C.DANGER}[ERROR] Query failed: {e}{C.RESET}\n")


# ==============================================================================
# Main Interactive Console REPL
# ==============================================================================

def main():
    """Main workstation supervisor loop."""
    repo_root = BASE_DIR.parent if BASE_DIR.name == "backend" else BASE_DIR
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"

    # Handle direct diagnostic flags
    if "--doctor" in sys.argv or "--diag" in sys.argv:
        run_system_doctor()
        return

    if "--status" in sys.argv or "-s" in sys.argv:
        print_live_status_dashboard()
        return

    print_banner()

    # Pre-clean ports
    free_port(8000)
    free_port(5173)

    # Initialize supervisor
    python_exe = sys.executable
    supervisor = DualProcessSupervisor(
        backend_dir=backend_dir,
        frontend_dir=frontend_dir,
        python_exe=python_exe,
    )

    # Register exit signal handlers
    def _sig_handler(sig, frame):
        supervisor.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    try:
        signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass

    # 1. Launch Backend
    print_supervisor_event(format_stream_row(TAG_FAST, "Launching Backend on http://localhost:8000..."))
    if not supervisor.start_backend():
        print(f"{C.DANGER}[FATAL] Could not launch backend server.{C.RESET}")
        return

    backend_timeout = int(os.getenv("RAISE_BACKEND_TIMEOUT", "180"))
    if not supervisor.wait_for_backend(timeout_sec=backend_timeout):
        print(f"{C.DANGER}[FATAL] Backend failed to become healthy. Check backend.log for tracebacks.{C.RESET}")
        supervisor.shutdown()
        return
    print_supervisor_event(format_stream_row(TAG_READY, "Backend Gateway is LIVE on http://localhost:8000"))

    # 2. Launch Frontend
    print_supervisor_event(format_stream_row(TAG_FAST, "Launching Frontend on http://localhost:5173..."))
    if not supervisor.start_frontend():
        print(f"{C.DANGER}[FATAL] Could not launch frontend server.{C.RESET}")
        supervisor.shutdown()
        return

    if not supervisor.wait_for_frontend(timeout_sec=35):
        print_supervisor_event(format_stream_row(TAG_WARN, "Frontend taking longer to initialize. Continuing..."))
    else:
        print_supervisor_event(format_stream_row(TAG_READY, "Frontend Workstation is LIVE on http://localhost:5173"))

    # Launch browser if not disabled
    no_browser = any(arg in sys.argv for arg in ("--no-browser", "-nb", "--nobrowser"))
    if not no_browser:
        target_url = "http://localhost:5173"
        try:
            import webbrowser
            webbrowser.open(target_url)
            print_supervisor_event(format_stream_row(TAG_SYNC, f"Browser opened to {target_url}."))
        except Exception:
            pass

    # Print Live Status Dashboard
    focused_doc: Optional[str] = None
    print_live_status_dashboard(focused_doc=focused_doc)

    print(DIM + "╭─" + "─" * 74 + "╮" + C.RESET)
    print(f"{DIM}│{C.RESET}  {C.TITLE}💬 RAISE INTERACTIVE TERMINAL READY{C.RESET}{' ' * 37}{DIM}│{C.RESET}")
    print(f"{DIM}│{C.RESET}  {C.MUTED}Type a question, 'status' for telemetry, 'doctor' to test, or 'exit'{C.RESET}{' ' * 5}{DIM}│{C.RESET}")
    print(DIM + "╰─" + "─" * 74 + "╯" + C.RESET + "\n")

    # Non-blocking interactive input bar using prompt_toolkit with patch_stdout
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit.formatted_text import ANSI
        has_pt = True
    except ImportError:
        has_pt = False

    if has_pt:
        pt_session = PromptSession()
        with patch_stdout(raw=True):
            while True:
                try:
                    scope_badge = f"{focused_doc}" if focused_doc else "ALL DOCS"
                    prompt_str = (
                        f"{DIM}╭─{C.RESET} {C.ACCENT}RAISE{C.RESET} [{C.TITLE}{scope_badge}{C.RESET}] {DIM}─╮{C.RESET}\n"
                        f"{DIM}╰─>{C.RESET} "
                    )
                    user_input = pt_session.prompt(ANSI(prompt_str)).strip()
                    if not user_input:
                        continue
                    should_exit, focused_doc = dispatch_repl_command(user_input, focused_doc, supervisor)
                    if should_exit:
                        break
                except (KeyboardInterrupt, EOFError):
                    break
                except Exception as err:
                    print(f"{C.DANGER}[ERROR] Console error: {err}{C.RESET}")
    else:
        while True:
            try:
                scope_badge = f"{focused_doc}" if focused_doc else "ALL DOCS"
                prompt_str = f"RAISE [{C.ACCENT}{scope_badge}{C.RESET}] > "
                
                global _active_repl_prompt
                _active_repl_prompt = prompt_str
                try:
                    user_input = input(prompt_str).strip()
                finally:
                    _active_repl_prompt = None

                if not user_input:
                    continue

                should_exit, focused_doc = dispatch_repl_command(user_input, focused_doc, supervisor)
                if should_exit:
                    break
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as err:
                print(f"{C.DANGER}[ERROR] Console error: {err}{C.RESET}")

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
        print(f"\n{C.TITLE}⚡ Running Quick 3-Query Benchmark Verification...{C.RESET}")
        sample_queries = [
            "What is the primary mission or purpose of the institution?",
            "What are the major academic programmes offered?",
            "Summarize key research and industry collaboration highlights.",
        ]
        for q in sample_queries:
            execute_terminal_query(q, focused_doc=focused_doc)
    else:
        # Regular user query
        execute_terminal_query(user_input, focused_doc=focused_doc)

    return False, focused_doc


if __name__ == "__main__":
    main()
