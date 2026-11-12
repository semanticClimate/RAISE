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

# Ensure UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

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

logger = logging.getLogger("RAISE_ServiceRunner")


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
    """Renders the top-level RAISE workstation banner."""
    print("\n" + C.BANNER + "╔" + "═" * 76 + "╗" + C.RESET)
    print(f"{C.BANNER}║{C.RESET}  {C.TITLE}🚀 RAISE ACADEMIC GRAPHRAG STUDIO{C.RESET} — {C.CYAN}MONOREPO WORKSTATION{C.RESET}{' ' * 16}{C.BANNER}║{C.RESET}")
    print(f"{C.BANNER}║{C.RESET}  {C.MUTED}Backend API : http://localhost:8000   | Swagger Docs: http://localhost:8000/docs{C.RESET}{C.BANNER}║{C.RESET}")
    print(f"{C.BANNER}║{C.RESET}  {C.MUTED}Frontend UI : http://localhost:5173   | Architecture: Hybrid GraphRAG + NLI{C.RESET}{C.BANNER}║{C.RESET}")
    print(C.BANNER + "╚" + "═" * 76 + "╝" + C.RESET + "\n")


def print_live_status_dashboard(focused_doc: Optional[str] = None) -> None:
    """Renders real-time diagnostic dashboard modeled from dev_main.py."""
    print(C.BANNER + "╔" + "═" * 76 + "╗" + C.RESET)
    print(f"{C.BANNER}║{C.RESET} {C.TITLE}🩺  RAISE WORKSTATION HEALTH & SUBSYSTEM DIAGNOSTICS{C.RESET}{' ' * 23}{C.BANNER}║{C.RESET}")

    # 1. Hardware Summary
    hw = fetch_json_endpoint("http://127.0.0.1:8000/api/system/hardware")
    if hw:
        gpu_str = f"{hw.get('gpu_name', 'None')} ({hw.get('vram_gb', 0)}GB VRAM)" if hw.get("cuda_available") else "CPU Only (CUDA Inactive)"
        ram_str = f"{hw.get('available_ram_gb', 0):.1f} GB avail / {hw.get('total_ram_gb', 0):.1f} GB total"
        hw_line = f"GPU: {gpu_str} | RAM: {ram_str} ({hw.get('cpu_count', 0)} Cores)"
    else:
        hw_line = "Probing system hardware..."
    print(f"{C.BANNER}║{C.RESET} {C.MUTED}Hardware: {hw_line}{C.RESET}")
    print(C.BANNER + "╠" + "═" * 76 + "╣" + C.RESET)

    # 2. Subsystems
    # Backend Config & Models
    cfg = fetch_json_endpoint("http://127.0.0.1:8000/api/system/config")
    synth = get_synthesizer_status()

    # ChromaDB Count
    chroma_count = 0
    chroma_model = "bge-base-en-v1.5"
    chroma_online = False
    try:
        from src.infrastructure.vector.chroma import LocalVectorEngine
        ve = LocalVectorEngine()
        if ve.collection:
            chroma_count = ve.collection.count()
            chroma_model = ve.model_key
            chroma_online = True
    except Exception:
        pass

    # Neo4j Graph Probe
    neo4j_online = is_port_open(7687)
    neo4j_str = f"{C.SUCCESS}CONNECTED (bolt://localhost:7687){C.RESET}" if neo4j_online else f"{C.WARN}OFFLINE (In-memory graph active){C.RESET}"
    chroma_str = f"{C.SUCCESS}ACTIVE ({chroma_count} indexed chunks | {chroma_model}){C.RESET}" if chroma_online else f"{C.WARN}EMPTY / OFFLINE{C.RESET}"
    synth_str = synth.get("display_string", f"{C.SUCCESS}ACTIVE{C.RESET}")

    print(f"{C.BANNER}║{C.RESET} {C.SECTION}SUBSYSTEM STATUS:{C.RESET}")
    print(f"{C.BANNER}║{C.RESET}   • ChromaDB Vector Store     : {chroma_str}")
    print(f"{C.BANNER}║{C.RESET}   • Neo4j Graph Database      : {neo4j_str}")
    print(f"{C.BANNER}║{C.RESET}   • Active LLM Synthesizer    : {synth_str}")
    if cfg:
        print(f"{C.BANNER}║{C.RESET}   • Embedding Neural Model    : {C.WHITE}{cfg.get('embedding_model', 'bge-base')}{C.RESET}")
        print(f"{C.BANNER}║{C.RESET}   • Neural Reranker Model     : {C.WHITE}{cfg.get('reranker_model', 'jina-reranker-v3.5')}{C.RESET}")
        print(f"{C.BANNER}║{C.RESET}   • NLI Entailment Verifier   : {C.WHITE}{cfg.get('nli_verifier_model', 'finecat-nli-ultra-l')}{C.RESET}")

    # Active Documents
    docs = get_active_documents_list()
    print(f"{C.BANNER}║{C.RESET}")
    print(f"{C.BANNER}║{C.RESET} {C.SECTION}REGISTERED DOCUMENT LIBRARY ({len(docs)} documents):{C.RESET}")
    if docs:
        for idx, d in enumerate(docs[:8], 1):
            fn = d.get("filename", "document.pdf")
            short_fn = fn if len(fn) <= 38 else fn[:35] + "..."
            pgs = d.get("pages", 0)
            chks = d.get("chunks_count", 0)
            sz = f"{d.get('size_mb', 0):.1f}MB"
            print(f"{C.BANNER}║{C.RESET}   [{C.NUM}{idx}{C.RESET}] {C.WHITE}{short_fn:<38}{C.RESET} {C.NUM}{pgs:>3}p{C.RESET} | {C.NUM}{chks:>3} chks{C.RESET} | {sz:>7}")
        if len(docs) > 8:
            print(f"{C.BANNER}║{C.RESET}   ... and {len(docs) - 8} more documents (use 'docs' to list all)")
    else:
        print(f"{C.BANNER}║{C.RESET}   {C.WARN}⚠️  No documents in catalog. Upload PDFs via Web UI or 'upload <path>'{C.RESET}")

    scope_name = f"'{focused_doc}' (Single Document Target)" if focused_doc else "ALL REGISTERED DOCUMENTS (Multi-Hop Graph Scope)"
    print(f"{C.BANNER}║{C.RESET}")
    print(f"{C.BANNER}║{C.RESET} {C.SECTION}INTERACTIVE CONSOLE STATE:{C.RESET}")
    print(f"{C.BANNER}║{C.RESET}   • Active Research Scope     : {C.ACCENT}{scope_name}{C.RESET}")
    print(f"{C.BANNER}║{C.RESET}   • Web UI Link               : {C.CYAN}http://localhost:5173{C.RESET}")
    print(C.BANNER + "╚" + "═" * 76 + "╝" + C.RESET + "\n")


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
    neo_badge = f"{C.SUCCESS}ONLINE (Port 7687 responding){C.RESET}" if neo_ok else f"{C.WARN}OFFLINE (In-memory fallback){C.RESET}"
    print(f"  • {'Neo4j Database (:7687)':<32} : {neo_badge}")

    redis_ok = is_port_open(6379)
    redis_badge = f"{C.SUCCESS}ONLINE (Port 6379 responding){C.RESET}" if redis_ok else f"{C.MUTED}INACTIVE (In-memory fallback){C.RESET}"
    print(f"  • {'Redis Cache (:6379)':<32} : {redis_badge}")

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

    def start_backend(self) -> bool:
        """Starts the FastAPI backend service."""
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
            )
            # Start background reader threads
            threading.Thread(target=self._stream_output, args=(self.backend_proc.stdout, "BACKEND", False), daemon=True).start()
            threading.Thread(target=self._stream_output, args=(self.backend_proc.stderr, "BACKEND-ERR", True), daemon=True).start()
            return True
        except Exception as e:
            print(f"{C.DANGER}[ERROR] Failed to start backend: {e}{C.RESET}")
            return False

    def start_frontend(self) -> bool:
        """Starts the React / Vite frontend service."""
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
            )
            # Start background reader threads
            threading.Thread(target=self._stream_output, args=(self.frontend_proc.stdout, "FRONTEND", False), daemon=True).start()
            threading.Thread(target=self._stream_output, args=(self.frontend_proc.stderr, "FRONTEND-ERR", True), daemon=True).start()
            return True
        except Exception as e:
            print(f"{C.DANGER}[ERROR] Failed to start frontend: {e}{C.RESET}")
            return False

    def _stream_output(self, stream, prefix: str, is_err: bool):
        """Reads process output line by line and appends to log buffers."""
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

                # Format and print important operational lines
                clean_line = sanitize_text(line)
                if is_err:
                    if any(kw in clean_line.lower() for kw in ("error", "traceback", "exception", "failed")):
                        print(f"{C.DANGER}[{prefix}] {clean_line}{C.RESET}")
                    elif "warning" in clean_line.lower():
                        print(f"{C.WARN}[{prefix}] {clean_line}{C.RESET}")
                    elif any(kw in clean_line for kw in ("Loading weights", "it/s", "%|")):
                        print(f"{C.CYAN}[MODEL-LOAD] {clean_line}{C.RESET}")
                else:
                    if any(kw in clean_line for kw in ("POST /", "GET /", "OPTIONS /")):
                        print(f"{C.CYAN}[API] {clean_line}{C.RESET}")
                    elif "[INFERENCE]" in clean_line or "Executing task" in clean_line:
                        print(f"{C.SUCCESS}[INFERENCE] {clean_line}{C.RESET}")
                    elif "ready in" in clean_line or "Local:" in clean_line:
                        print(f"{C.SUCCESS}[FRONTEND] {clean_line}{C.RESET}")
                    elif any(kw in clean_line.lower() for kw in ("error", "failed", "crash")):
                        print(f"{C.DANGER}[{prefix}] {clean_line}{C.RESET}")

    def wait_for_backend(self, timeout_sec: int = 45) -> bool:
        """Polls /api/health until the backend gateway is alive."""
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            if self.backend_proc and self.backend_proc.poll() is not None:
                return False
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"User-Agent": "RAISE-Supervisor"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(0.8)
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
        "mode": "deep",
        "stream": False,
        "active_docs": active_docs,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "RAISE-Terminal"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60.0) as resp:
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
    print(f"{C.CYAN}[RAISE] Launching Backend on http://localhost:8000...{C.RESET}")
    if not supervisor.start_backend():
        print(f"{C.DANGER}[FATAL] Could not launch backend server.{C.RESET}")
        return

    if not supervisor.wait_for_backend(timeout_sec=45):
        print(f"{C.DANGER}[FATAL] Backend failed to become healthy. Check backend.log for tracebacks.{C.RESET}")
        supervisor.shutdown()
        return
    print(f"{C.SUCCESS}[RAISE] Backend Gateway is LIVE on http://localhost:8000{C.RESET}")

    # 2. Launch Frontend
    print(f"{C.CYAN}[RAISE] Launching Frontend on http://localhost:5173...{C.RESET}")
    if not supervisor.start_frontend():
        print(f"{C.DANGER}[FATAL] Could not launch frontend server.{C.RESET}")
        supervisor.shutdown()
        return

    if not supervisor.wait_for_frontend(timeout_sec=35):
        print(f"{C.WARN}[NOTICE] Frontend taking longer to initialize. Continuing...{C.RESET}")
    else:
        print(f"{C.SUCCESS}[RAISE] Frontend Workstation is LIVE on http://localhost:5173{C.RESET}")

    # Launch browser if not disabled
    no_browser = any(arg in sys.argv for arg in ("--no-browser", "-nb", "--nobrowser"))
    if not no_browser:
        target_url = "http://localhost:5173"
        try:
            import webbrowser
            webbrowser.open(target_url)
            print(f"{C.MUTED}[NOTE] Browser opened to {target_url}. Terminal is ready for commands!{C.RESET}")
        except Exception:
            pass

    # Print Live Status Dashboard
    focused_doc: Optional[str] = None
    print_live_status_dashboard(focused_doc=focused_doc)

    print(C.BANNER + "═" * 76 + C.RESET)
    print(f" {C.TITLE}💬 RAISE INTERACTIVE TERMINAL READY{C.RESET}")
    print(f" {C.MUTED}Type a question to run research, 'status' for telemetry, 'doctor' to test, or 'exit'{C.RESET}")
    print(C.BANNER + "═" * 76 + C.RESET + "\n")

    # Interactive REPL Loop
    while True:
        try:
            scope_badge = f"{focused_doc}" if focused_doc else "ALL DOCS"
            prompt_str = f"RAISE [{C.ACCENT}{scope_badge}{C.RESET}] > "
            
            user_input = input(prompt_str).strip()
            if not user_input:
                continue

            cmd_lower = user_input.lower()

            if cmd_lower in ("exit", "quit", "q", ":q"):
                break
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

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{C.DANGER}[ERROR] Console error: {err}{C.RESET}")

    supervisor.shutdown()


if __name__ == "__main__":
    main()
