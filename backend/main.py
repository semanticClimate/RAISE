"""
RAISE — Master Terminal & Interactive Research Studio (v1.0.0 Enterprise-Tier)
======================================================================
High-performance terminal CLI runner providing:
1. Subsystem Diagnostics & Health Monitoring (Neo4j, ChromaDB, vLLM, Redis)
2. Dual-Tier Conversational Memory & Dynamic Intent Routing
3. Fast (PyMuPDF) vs Deep (IBM Docling TableFormer) Document Ingestion
4. Strict Drawer Isolation & Scoped Multi-Hop GraphRAG Retrieval
5. Neural Grounding with Qwen 2.5 14B, In-Line Citations & Math Auditing
6. Full Privacy Sanitization (zero personal usernames or local path leakage)
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Enforce UTF-8 console output for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure RAG project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Enable native ANSI color support on Windows
try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass

try:
    os.system("")  # Enables ENABLE_VIRTUAL_TERMINAL_PROCESSING
except Exception:
    pass

# Load environment variables
try:
    from dotenv import load_dotenv
    _env_path = BASE_DIR / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
    else:
        load_dotenv()
except Exception:
    pass

# Logging setup
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline.log"

logger = logging.getLogger("RAISE_Studio")
log_level_str = os.getenv("RAISE_LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, log_level_str, logging.INFO))

if not logger.handlers:
    file_handler = RotatingFileHandler(
        str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8", delay=True
    )
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Suppress informational notifications from Neo4j driver (e.g. index already exists alerts)
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)

# Modular imports & public API re-exports for 100% backward compatibility
from src.cli.commands import sanitize_path
from src.cli.document_manager import (
    check_document_is_protected,
    get_active_documents_list,
    ingest_pdf_from_path,
    list_active_documents,
    remove_document_from_library,
    remove_document_from_vault,
)
from src.cli.interactive_repl import run_interactive_studio
from src.cli.persona_classifier import NON_NAME_TOKENS, extract_conversational_persona
from src.cli.renderer import C
import argparse
from src.cli.status_dashboard import print_help_menu, print_system_status
from src.cli.system_launcher import auto_start_containers, check_vllm_health, get_synthesizer_status
from src.features.memory.reasoning import ReasoningMemory
from src.features.verification.math_engine import DeterministicMathEngine
from src.retrieval.pipeline import StandaloneRAGPipeline

__all__ = [
    "BASE_DIR",
    "LOG_DIR",
    "LOG_FILE",
    "auto_start_containers",
    "check_vllm_health",
    "get_synthesizer_status",
    "get_active_documents_list",
    "list_active_documents",
    "check_document_is_protected",
    "remove_document_from_library",
    "remove_document_from_vault",
    "ingest_pdf_from_path",
    "extract_conversational_persona",
    "print_system_status",
    "print_help_menu",
    "NON_NAME_TOKENS",
    "StandaloneRAGPipeline",
    "ReasoningMemory",
    "DeterministicMathEngine",
    "build_cli_parser",
    "main",
]


def build_cli_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser for RAISE CLI."""
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="RAISE (v1.0.0) — Research Assessment Intelligence & Semantic Extraction",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="Display user command reference and command-line usage.")
    parser.add_argument("-s", "--status", action="store_true", help="Display live multi-substrate subsystem diagnostics and exit.")
    parser.add_argument("-c", "--clear-cache", action="store_true", help="Clear reasoning memory trajectories and session cache.")
    parser.add_argument("-q", "--query", type=str, default=None, help="Execute a single grounded research query and exit.")
    parser.add_argument("-p", "--provider", "--llm", dest="provider", type=str, default=None, help="Specify LLM inference backend (groq, gemini, vllm, deepseek, nvidia, cohere, openrouter).")
    parser.add_argument("--auto-start", "--start-containers", dest="auto_start", action="store_true", help="Auto-start Docker containers for Neo4j and vLLM if offline.")
    parser.add_argument("--gui", "--ui", action="store_true", help="Launch GUI selector for inference backend.")
    parser.add_argument("documents", nargs="*", default=[], help="Optional PDF file path(s) to ingest on startup.")
    return parser


def main() -> int:
    """Master entrypoint for RAISE Studio CLI."""
    parser = build_cli_parser()
    args, unknown = parser.parse_known_args()

    # Fast-path 1: Help Menu (instant, 0.05s, zero heavy imports or container boots)
    if args.help:
        print_help_menu()
        return 0

    # Fast-path 2: Subsystem Status Diagnostics
    if args.status:
        print(C.BANNER + "═" * 74 + C.RESET)
        print(f" {C.TITLE}🚀 RAISE (v1.0.0){C.RESET} — {C.CYAN}RESEARCH ASSESSMENT INTELLIGENCE & SEMANTIC EXTRACTION{C.RESET}")
        print(C.BANNER + "═" * 74 + C.RESET)
        print_system_status()
        return 0

    print(C.BANNER + "═" * 74 + C.RESET)
    print(f" {C.TITLE}🚀 RAISE (v1.0.0){C.RESET} — {C.CYAN}RESEARCH ASSESSMENT INTELLIGENCE & SEMANTIC EXTRACTION{C.RESET}")
    print(C.BANNER + "═" * 74 + C.RESET)

    # Only auto-start containers if explicitly requested by user
    if args.auto_start:
        auto_start_containers()

    # Configure LLM Inference Backend (Local vLLM vs Cloud APIs)
    try:
        from src.cli.llm_selector import prompt_llm_backend, show_simple_gui_prompt
        if args.gui:
            show_simple_gui_prompt()
        elif args.provider:
            from src.cli.llm_selector import _apply_provider_choice
            from src.infrastructure.providers.router import get_provider_router
            _apply_provider_choice(args.provider, get_provider_router())
        else:
            prompt_llm_backend()
    except Exception as _sel_err:
        logger.debug(f"LLM selection notice: {_sel_err}")

    print(f"\n{C.SECTION}[1/2] Initializing Multi-Substrate Pipeline (Vector + Neo4j + LangGraph)...{C.RESET}")
    pipeline = StandaloneRAGPipeline()
    memory = ReasoningMemory()

    # Clear reasoning memory cache if requested
    if args.clear_cache:
        memory.clear()
        if hasattr(pipeline, "reasoning_memory"):
            pipeline.reasoning_memory.clear()
        print(f"{C.SUCCESS}🧹 [Cache Cleared]{C.RESET} Reasoning memory trajectories reset.")

    # Verify Neo4j connectivity and schema index
    if pipeline.neo4j_db.connected:
        try:
            from src.infrastructure.graph.schema import ensure_basic_indexes
            ensure_basic_indexes(pipeline.neo4j_db)
            neo4j_status = f"{C.SUCCESS}CONNECTED & INDEXED{C.RESET} {C.MUTED}(bolt://localhost:7687){C.RESET}"
        except Exception as e:
            neo4j_status = f"{C.SUCCESS}CONNECTED{C.RESET} {C.MUTED}(Index note: {e}){C.RESET}"
    else:
        neo4j_status = f"{C.WARN}OFFLINE{C.RESET} {C.MUTED}(In-memory graph active){C.RESET}"

    # ChromaDB status (distinguish READY, EMPTY, OFFLINE)
    try:
        chroma_col = pipeline.vector_engine.collection
        chroma_count = chroma_col.count() if chroma_col else 0
        if chroma_col is None:
            chroma_status = f"{C.DANGER}OFFLINE{C.RESET} {C.MUTED}(Vector store unavailable){C.RESET}"
        elif chroma_count == 0:
            chroma_status = f"{C.WARN}EMPTY{C.RESET} {C.MUTED}(0 indexed chunks — upload or ingest PDFs to begin){C.RESET}"
        else:
            chroma_status = f"{C.SUCCESS}READY{C.RESET} {C.MUTED}({chroma_count} indexed chunks){C.RESET}"
    except Exception as _c_err:
        chroma_status = f"{C.DANGER}OFFLINE{C.RESET} {C.MUTED}({_c_err}){C.RESET}"

    active_docs = pipeline.vector_engine.get_active_workspace_documents()
    synth_info = get_synthesizer_status()

    print(f"  • {C.MUTED}Neo4j Graph:{C.RESET}        {neo4j_status}")
    print(f"  • {C.MUTED}ChromaDB Vector:{C.RESET}    {chroma_status}")
    print(f"  • {C.MUTED}Embeddings Model:{C.RESET}   {C.ACCENT}{pipeline.vector_engine.model_key}{C.RESET}")
    print(f"  • {C.MUTED}Synthesizer:{C.RESET}        {synth_info['display_string']}")
    print(f"  • {C.MUTED}Library Manifest:{C.RESET}   {C.NUM}{len(active_docs)}{C.RESET} {C.MUTED}document(s) loaded{C.RESET}")

    focused_document: Optional[str] = active_docs[-1] if active_docs else None

    # Handle document ingestion from positional arguments or unknown file arguments
    docs_to_ingest = list(args.documents)
    for u in unknown:
        cleaned_u = u.strip().strip("'\"")
        if cleaned_u.lower().endswith(".pdf") or Path(cleaned_u).is_file():
            docs_to_ingest.append(cleaned_u)

    for doc_candidate in docs_to_ingest:
        doc_candidate = doc_candidate.strip().strip("'\"")
        if doc_candidate.lower().endswith(".pdf") or Path(doc_candidate).is_file():
            print(f"\n{C.SECTION}[CLI Argument Detected]:{C.RESET} Ingesting '{C.WHITE}{sanitize_path(doc_candidate)}{C.RESET}'...")
            new_doc = ingest_pdf_from_path(doc_candidate, pipeline)
            if new_doc:
                focused_document = new_doc
            break

    # Execute interactive studio REPL or single query
    run_interactive_studio(
        pipeline=pipeline,
        memory=memory,
        focused_document=focused_document,
        cli_query=args.query,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())