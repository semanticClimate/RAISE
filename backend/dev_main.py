"""
RAISE — Developer & Deep Observability Console (dev_main.py)
=============================================================
Modular, high-performance CLI research studio and forensic terminal REPL.
Features:
1. Complete decoupled data/presentation architecture (Pipeline -> TelemetryFrame -> Renderer).
2. Honest forensic metric states (MEASURED, DERIVED, ESTIMATED, UNAVAILABLE, NOT_APPLICABLE).
3. Zero silent fake-number synthesis.
4. Interactive research studio with drawer attachment, document scoping, and live diagnostics.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Enforce UTF-8 console output for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Enable native ANSI color support
try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

try:
    from prompts.system_synthesis import sanitize_rag_text
except ImportError:
    def sanitize_rag_text(text: str) -> str:
        if not text:
            return ""
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        clean = re.sub(r"\r\n|\r", "\n", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return clean.strip()

from main import (
    auto_start_containers,
    extract_conversational_persona,
    get_active_documents_list,
    ingest_pdf_from_path,
    list_active_documents,
)
from src.cli.commands import (
    SessionTracker,
    execute_dev_purge_all,
    print_dev_help_menu,
    print_system_dashboard,
    sanitize_path,
)
from src.cli.dev_repl import run_dev_repl
from src.cli.models import TelemetryFrame
from src.cli.renderer import C, ObsMode, TelemetryRenderer
from src.cli.telemetry_service import TelemetryService
from src.features.memory.reasoning import ReasoningMemory
from src.retrieval.pipeline import StandaloneRAGPipeline

logger = logging.getLogger("RAISE_DevStudio")

# Suppress informational notifications from Neo4j driver (e.g. index already exists alerts)
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)

__all__ = [
    "BASE_DIR",
    "StandaloneRAGPipeline",
    "ReasoningMemory",
    "TelemetryFrame",
    "TelemetryService",
    "TelemetryRenderer",
    "ObsMode",
    "SessionTracker",
    "auto_start_containers",
    "get_active_documents_list",
    "list_active_documents",
    "ingest_pdf_from_path",
    "extract_conversational_persona",
    "execute_dev_purge_all",
    "print_dev_help_menu",
    "print_system_dashboard",
    "sanitize_path",
    "sanitize_rag_text",
    "main",
]


def main():
    print(C.BANNER + "═" * 78 + C.RESET)
    print(f" {C.TITLE}🔧 RAISE DEV STUDIO (v3.1){C.RESET} — {C.CYAN}FORENSIC OBSERVABILITY CONSOLE{C.RESET}")
    print(f" {C.MUTED}Architecture: Decoupled TelemetryFrame | Honest Provenance Tagging | Anti-Hallucination{C.RESET}")
    print(C.BANNER + "═" * 78 + C.RESET)

    if "--help" in sys.argv or "-h" in sys.argv:
        print_dev_help_menu()
        return

    auto_start_containers()

    # Direct Neural Model Control Center launch flag
    if any(arg in sys.argv for arg in ("control-center", "--control-center", "ops", "--ops", "gui", "--gui", "--ui", "--control-panel", "-g")):
        try:
            from src.gui.control_panel import launch_model_control_center
            print(f"\n{C.SECTION}🖥️  Launching RAISE Neural Model Control Center...{C.RESET}")
            launch_model_control_center()
            return
        except Exception as _gui_err:
            print(f"Notice: Control Center launch error: {_gui_err}")

    # Configure LLM Inference Backend (Local vLLM vs Cloud APIs)
    try:
        from src.cli.llm_selector import prompt_llm_backend
        prompt_llm_backend()
    except Exception as _sel_err:
        logger.debug(f"LLM selection notice: {_sel_err}")

    print(f"\n{C.SECTION}[1/2] Initializing Multi-Substrate Pipeline & Telemetry Service...{C.RESET}")
    pipeline = StandaloneRAGPipeline()
    memory = ReasoningMemory()
    session = SessionTracker(mode=ObsMode.TRACE)

    focused_document: Optional[str] = None
    user_persona_name: Optional[str] = None

    # Handle direct PDF ingestion CLI flags (--ingest / --upload)
    if "--ingest" in sys.argv or "--upload" in sys.argv:
        u_flag = "--ingest" if "--ingest" in sys.argv else "--upload"
        u_idx = sys.argv.index(u_flag)
        if u_idx + 1 < len(sys.argv):
            target_pdf = sys.argv[u_idx + 1].strip()
            selected_engine = "fast"
            if "--engine" in sys.argv:
                e_idx = sys.argv.index("--engine")
                if e_idx + 1 < len(sys.argv):
                    selected_engine = sys.argv[e_idx + 1].strip().lower()
            target_pages = 0
            if "--pages" in sys.argv:
                p_idx = sys.argv.index("--pages")
                if p_idx + 1 < len(sys.argv):
                    p_val = sys.argv[p_idx + 1].strip()
                    try:
                        target_pages = int(p_val) if p_val.isdigit() else 0
                    except ValueError:
                        target_pages = 0
            print(f"\n{C.SECTION}📥 [Ingest] Ingesting PDF report:{C.RESET} {C.WHITE}{target_pdf}{C.RESET}")
            new_doc = ingest_pdf_from_path(target_pdf, pipeline, engine=selected_engine, max_pages=target_pages)
            if new_doc:
                print(f"\n{C.SUCCESS}✨ [Ingest] Successfully ingested and synced to ChromaDB & Neo4j:{C.RESET} {new_doc}\n")
            return

    # Handle automated benchmark suite CLI flags (--benchmark [raise|frames], --limit N)
    if any(flag in sys.argv for flag in ("--benchmark", "-b", "--bench")):
        b_flag = next(f for f in ("--benchmark", "-b", "--bench") if f in sys.argv)
        b_idx = sys.argv.index(b_flag)
        bench_type = "raise"
        if b_idx + 1 < len(sys.argv) and not sys.argv[b_idx + 1].startswith("-"):
            bench_type = sys.argv[b_idx + 1].strip().lower()

        limit = None
        if "--limit" in sys.argv:
            l_idx = sys.argv.index("--limit")
            if l_idx + 1 < len(sys.argv) and sys.argv[l_idx + 1].isdigit():
                limit = int(sys.argv[l_idx + 1])

        from src.cli.benchmark_runner import run_dev_benchmark
        run_dev_benchmark(pipeline, memory, session, benchmark_type=bench_type, limit=limit)
        return

    # Status / Diagnostic flag
    if "--status" in sys.argv or "-s" in sys.argv:
        print_system_dashboard(pipeline, memory, session, focused_document)
        return

    # Hard reset / purge flag
    if "--purge-all" in sys.argv or "--hard-reset" in sys.argv:
        execute_dev_purge_all(pipeline, memory)
        return

    # Render dashboard for interactive REPL session
    print_system_dashboard(pipeline, memory, session, focused_document)

    # Handle mode CLI flag
    if "--mode" in sys.argv or "-m" in sys.argv:
        m_flag = "--mode" if "--mode" in sys.argv else "-m"
        m_idx = sys.argv.index(m_flag)
        if m_idx + 1 < len(sys.argv):
            m_val = sys.argv[m_idx + 1].strip().upper()
            try:
                session.mode = ObsMode[m_val]
                print(f"🎯 [Mode Initialized]: {session.mode.value}\n")
            except Exception:
                pass

    # Handle attach CLI flag
    if "--attach" in sys.argv or "-a" in sys.argv:
        a_flag = "--attach" if "--attach" in sys.argv else "-a"
        a_idx = sys.argv.index(a_flag)
        if a_idx + 1 < len(sys.argv):
            target_att = sys.argv[a_idx + 1].strip()
            manifest_docs = get_active_documents_list()
            resolved = None
            if target_att.isdigit():
                idx = int(target_att) - 1
                if 0 <= idx < len(manifest_docs):
                    resolved = manifest_docs[idx].get("filename")
            else:
                for d in manifest_docs:
                    fn = d.get("filename", "")
                    if target_att.lower() in fn.lower():
                        resolved = fn
                        break
            if resolved:
                focused_document = resolved
                print(f"🎯 [Active Scope Attached]: {C.ACCENT}'{focused_document}'{C.RESET}\n")

    # Handle query CLI flag
    cli_query = None
    if "--query" in sys.argv:
        q_idx = sys.argv.index("--query")
        if q_idx + 1 < len(sys.argv):
            cli_query = sys.argv[q_idx + 1]
    elif "-q" in sys.argv:
        q_idx = sys.argv.index("-q")
        if q_idx + 1 < len(sys.argv):
            cli_query = sys.argv[q_idx + 1]
    elif len(sys.argv) > 1:
        pos_tokens = []
        skip_next = False
        for a in sys.argv[1:]:
            if skip_next:
                skip_next = False
                continue
            if a in ("--attach", "-a", "--mode", "-m"):
                skip_next = True
                continue
            if not a.startswith("-") and not a.lower().endswith(".pdf") and not Path(a).is_file():
                pos_tokens.append(a)
        if pos_tokens:
            cli_query = " ".join(pos_tokens)

    # Launch interactive developer REPL
    run_dev_repl(
        pipeline=pipeline,
        memory=memory,
        session=session,
        focused_document=focused_document,
        user_persona_name=user_persona_name,
        cli_query=cli_query,
    )


if __name__ == "__main__":
    main()
