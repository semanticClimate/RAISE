"""
RAISE — Developer Observability REPL
====================================
Interactive research console REPL supporting granular observability modes (1-4),
honest telemetry extraction, anti-hallucination gates, and session tracing.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

from src.cli.commands import (
    execute_dev_purge_all,
    print_dev_help_menu,
    print_system_dashboard,
    sanitize_path,
)
from src.cli.document_manager import (
    get_active_documents_list as _fallback_get_docs,
    ingest_pdf_from_path as _fallback_ingest,
    list_active_documents as _fallback_list_docs,
)
from src.cli.persona_classifier import extract_conversational_persona
from src.cli.renderer import C, ObsMode, TelemetryRenderer
from src.cli.telemetry_service import TelemetryService


def _get_active_documents_list(*args, **kwargs):
    dm = sys.modules.get("dev_main")
    if dm and hasattr(dm, "get_active_documents_list"):
        return dm.get_active_documents_list(*args, **kwargs)
    return _fallback_get_docs(*args, **kwargs)


def _list_active_documents(*args, **kwargs):
    dm = sys.modules.get("dev_main")
    if dm and hasattr(dm, "list_active_documents"):
        return dm.list_active_documents(*args, **kwargs)
    return _fallback_list_docs(*args, **kwargs)


def _ingest_pdf_from_path(*args, **kwargs):
    dm = sys.modules.get("dev_main")
    if dm and hasattr(dm, "ingest_pdf_from_path"):
        return dm.ingest_pdf_from_path(*args, **kwargs)
    return _fallback_ingest(*args, **kwargs)

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

logger = logging.getLogger("RAISE_DevREPL")


def run_dev_repl(
    pipeline: Any,
    memory: Any,
    session: Any,
    focused_document: Optional[str] = None,
    user_persona_name: Optional[str] = None,
    cli_query: Optional[str] = None,
) -> None:
    """Executes the developer deep observability REPL turn loop."""
    print(C.BANNER + "═" * 78 + C.RESET)
    print(f" {C.TITLE}💬 RAISE RESEARCH STUDIO — INTERACTIVE OBSERVABILITY REPL{C.RESET}")
    print(f" {C.MUTED}Commands: 'docs', 'attach <N>', 'mode <1-4>', 'export', 'status', 'help', 'exit'{C.RESET}")
    print(C.BANNER + "═" * 78 + C.RESET)

    # Initialize non-blocking prompt session if prompt_toolkit is available
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit.formatted_text import ANSI
        has_pt = True
        pt_session = PromptSession()
    except ImportError:
        has_pt = False
        pt_session = None

    dim_border = "\033[38;5;240m"

    while True:
        try:
            scope_badge = f"{focused_document}" if focused_document else "ALL DOCUMENTS"
            prompt_label = (
                f"{dim_border}╭─{C.RESET} 🔬 [{C.ACCENT}{scope_badge}{C.RESET} | {C.NUM}{session.mode.value}{C.RESET}] {dim_border}─╮{C.RESET}\n"
                f"{dim_border}╰─>{C.RESET} "
            )
            if cli_query is not None:
                query = cli_query.strip()
                print(f"{prompt_label}{query}")
            elif has_pt and pt_session is not None:
                try:
                    with patch_stdout(raw=True):
                        query = pt_session.prompt(ANSI(prompt_label)).strip()
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{C.CYAN}Exiting RAISE Dev Studio. Goodbye!{C.RESET}")
                    break
            else:
                try:
                    query = input(prompt_label).strip()
                except EOFError:
                    print(f"\n{C.CYAN}Exiting RAISE Dev Studio. Goodbye!{C.RESET}")
                    break

            if not query:
                if cli_query is not None:
                    break
                continue

            q_lower = query.lower()

            if q_lower in ["exit", "quit", "q", ":q"]:
                print(f"\n{C.CYAN}Exiting RAISE Dev Studio. Goodbye!{C.RESET}")
                break

            if q_lower in ["help", "?", "commands"]:
                print_dev_help_menu()
                if cli_query is not None:
                    break
                continue

            if q_lower in ["status", "health", "info", "diag"]:
                print_system_dashboard(pipeline, memory, session, focused_document)
                if cli_query is not None:
                    break
                continue

            if q_lower in ["control-center", "control center", "ops", "model-center", "gui", "panel", "control panel", "operator", "ui"]:
                try:
                    from src.gui.control_panel import launch_model_control_center
                    print(f"\n{C.SECTION}🖥️  Launching RAISE Neural Model Control Center...{C.RESET}")
                    launch_model_control_center()
                    print(f"{C.SUCCESS}✨ [Control Center Closed] Returned to interactive console.{C.RESET}\n")
                except Exception as _gui_e:
                    print(f"\n{C.DANGER}⚠️  Failed to launch Control Center: {_gui_e}{C.RESET}\n")
                if cli_query is not None:
                    break
                continue

            if q_lower.startswith("mode ") or q_lower.startswith("m "):
                parts = query.split(None, 1)
                if len(parts) > 1:
                    m_arg = parts[1].strip().upper()
                    m_map = {
                        "1": ObsMode.NORMAL, "NORMAL": ObsMode.NORMAL,
                        "2": ObsMode.VERBOSE, "VERBOSE": ObsMode.VERBOSE,
                        "3": ObsMode.TRACE, "TRACE": ObsMode.TRACE, "DEEP TRACE": ObsMode.TRACE,
                        "4": ObsMode.DEBUG, "DEBUG": ObsMode.DEBUG, "RAW DEBUG": ObsMode.DEBUG,
                    }
                    if m_arg in m_map:
                        session.mode = m_map[m_arg]
                        print(f"\n{C.SUCCESS}✨ [OBSERVABILITY MODE UPDATED]{C.RESET} Active Mode: {C.NUM}{session.mode.value}{C.RESET}\n")
                    else:
                        print(f"\n{C.WARN}⚠️  Unknown mode '{m_arg}'. Options: 1(NORMAL), 2(VERBOSE), 3(TRACE), 4(DEBUG){C.RESET}\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["export", "export traces", "save trace"] or q_lower.startswith("export "):
                parts = query.split(None, 1)
                custom_fn = parts[1].strip() if len(parts) > 1 else None
                saved_path = session.export_traces(custom_fn)
                print(f"\n{C.SUCCESS}📁 [TELEMETRY EXPORTED]{C.RESET} Saved trace JSON to: {C.CYAN}{sanitize_path(saved_path)}{C.RESET}\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["docs", "list", "documents", "vault"]:
                _list_active_documents(focused_document)
                if cli_query is not None:
                    break
                continue

            if q_lower in ["clear chat", "clear history", "clear memory", "cls"]:
                pipeline.clear_chat_session()
                memory.clear()
                print(f"\n{C.SUCCESS}✨ [DEV CHAT & MEMORY CLEARED]{C.RESET} Session context reset.\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["purge all", "wipe all", "hard reset"]:
                success = execute_dev_purge_all(pipeline, memory)
                if success:
                    focused_document = None
                if cli_query is not None:
                    break
                continue

            if q_lower in ["attach all", "use all", "focus all", "select all", "scope all"]:
                focused_document = None
                print(f"🎯 [{C.SUCCESS}Scope Updated{C.RESET}]: Searching across {C.ACCENT}ALL documents{C.RESET}.\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["detach", "attach none", "detach all", "clear drawer"]:
                focused_document = "NONE"
                print(f"🎯 [{C.WARN}Drawer Emptied{C.RESET}]: No documents attached to drawer.\n")
                if cli_query is not None:
                    break
                continue

            if q_lower.startswith("attach ") or q_lower.startswith("use "):
                target = query.split(None, 1)[1].strip().strip("'\"")
                docs = _get_active_documents_list()
                resolved = None
                if target.isdigit():
                    idx = int(target) - 1
                    if 0 <= idx < len(docs):
                        resolved = docs[idx].get("filename")
                else:
                    for d in docs:
                        fn = d.get("filename", "")
                        if target.lower() in fn.lower():
                            resolved = fn
                            break
                if resolved:
                    focused_document = resolved
                    print(f"🎯 [{C.SUCCESS}Drawer Updated{C.RESET}]: Scope attached strictly to '{C.ACCENT}{focused_document}{C.RESET}'.\n")
                else:
                    print(f"{C.WARN}⚠️  No document matched '{target}'. Use 'docs' to view available IDs.{C.RESET}\n")
                if cli_query is not None:
                    break
                continue

            clean_potential_path = query.strip().strip("'\"")
            if clean_potential_path.lower().endswith(".pdf") and Path(clean_potential_path).is_file():
                print(f"\n{C.SECTION}📄 Detected PDF file path. Ingesting into library...{C.RESET}")
                new_doc = _ingest_pdf_from_path(clean_potential_path, pipeline)
                if new_doc:
                    focused_document = new_doc
                if cli_query is not None:
                    break
                continue

            if q_lower in ["upload", "add"]:
                try:
                    pdf_input = input(f"\n{C.SECTION}📄 Enter path to PDF report:{C.RESET} ").strip()
                except (EOFError, KeyboardInterrupt):
                    continue
                if pdf_input:
                    new_doc = _ingest_pdf_from_path(pdf_input, pipeline)
                    if new_doc:
                        focused_document = new_doc
                if cli_query is not None:
                    break
                continue

            if q_lower.startswith("upload ") or q_lower.startswith("add "):
                raw_arg = query.split(None, 1)[1].strip()
                new_doc = _ingest_pdf_from_path(raw_arg, pipeline)
                if new_doc:
                    focused_document = new_doc
                if cli_query is not None:
                    break
                continue

            # Query Execution & Telemetry Extraction
            t_turn_start = time.perf_counter()
            turn_id = session.next_turn_id()

            q_clean = query.strip()
            q_words = q_clean.split()
            is_potential_persona = (
                (len(q_words) <= 4 and "?" not in q_clean and not any(
                    term in q_clean.lower() for term in [
                        "campus", "located", "research", "admission", "examination", "nobel", "prize",
                        "annual", "report", "council", "institute", "science", "genome", "biotech",
                        "what", "where", "how", "which", "who", "why"
                    ]
                ))
                or any(q_clean.lower().startswith(p) for p in ["my name is", "call me ", "i am ", "i'm "])
            )
            persona_intent = extract_conversational_persona(query) if is_potential_persona else {"type": "research_query"}
            if persona_intent["type"] in ("name_intro", "greeting"):
                if persona_intent["type"] == "name_intro":
                    user_persona_name = persona_intent["name"]
                    answer_text = f"Hello {user_persona_name}! I am RAISE. How can I assist your research today?"
                else:
                    greet_suffix = f", {user_persona_name}" if user_persona_name else ""
                    answer_text = f"Hello{greet_suffix}! I am RAISE, running in Developer Observability mode. Please attach an academic report or ask any research inquiry."

                total_duration_ms = (time.perf_counter() - t_turn_start) * 1000.0
                frame = TelemetryService.build_frame(
                    result={
                        "grounded_answer": answer_text,
                        "query_intent": "CONVERSATIONAL",
                        "routing_strategy": "ZERO_DB_BYPASS",
                        "timings": {
                            "routing_ms": max(1.0, total_duration_ms * 0.8),
                            "synthesis_ms": max(1.0, total_duration_ms * 0.2),
                        },
                    },
                    query=query,
                    turn_id=turn_id,
                    session_id=session.session_id,
                    scope="CONVERSATIONAL",
                    mode=session.mode.value,
                )
                session.record_turn(frame)
                print(f"\n{C.TITLE}RAISE:{C.RESET} {answer_text}\n")
                TelemetryRenderer.render(frame, session.mode)
                if cli_query is not None:
                    break
                continue

            # Factual Document Research Query Boundary
            manifest_docs = _get_active_documents_list()
            if not manifest_docs or focused_document == "NONE":
                print(f"\n{C.WARN}⚠️  No active documents are currently attached to your drawer.{C.RESET}")
                print("   Please attach a document in your drawer to begin research.\n")
                if cli_query is not None:
                    break
                continue

            active_scoping = [focused_document] if focused_document else None
            scope_desc = f"'{focused_document}'" if focused_document else "ALL DOCUMENTS"
            print(f"\n{C.INFO}[LangGraph Executing Multi-Hop Retrieval (Target Scope: {C.ACCENT}{scope_desc}{C.INFO})...]{C.RESET}")

            res = pipeline.query_subgraph_graphrag(
                query=query,
                hops=2,
                top_k=6,
                document_filter=focused_document,
                active_docs=active_scoping,
            )
            total_duration_ms = (time.perf_counter() - t_turn_start) * 1000.0

            if not isinstance(res, dict):
                res = {"grounded_answer": str(res)}

            raw_answer = res.get("grounded_answer") or res.get("answer", "No response generated.")
            clean_answer = sanitize_rag_text(str(raw_answer))
            citations = res.get("citations") or []

            frame = TelemetryService.build_frame(
                result=res,
                query=query,
                turn_id=turn_id,
                session_id=session.session_id,
                scope=scope_desc,
                mode=session.mode.value,
            )
            if frame.performance.total_latency_ms == 0.0:
                frame.performance.total_latency_ms = total_duration_ms

            session.record_turn(frame)

            print("\n" + C.BANNER + "═" * 78 + C.RESET)
            print(f" {C.TITLE}📋 GROUNDED RESEARCH ANSWER{C.RESET} {C.MUTED}({total_duration_ms/1000.0:.2f}s | Gate: {frame.quality.decision.upper()}){C.RESET}")
            print(f" {C.MUTED}📄 Attached Document:{C.RESET} {C.ACCENT}{scope_desc}{C.RESET}")
            print(C.BANNER + "═" * 78 + C.RESET)

            colorized_answer = re.sub(
                r"\[(\d+(?:,\s*\d+)*)\]",
                lambda m: f"{C.CYAN}[{m.group(1)}]{C.RESET}",
                clean_answer,
            )
            print(colorized_answer + "\n")

            if citations:
                print(f"{C.SECTION}📚 Verified Citations & Provenance:{C.RESET}")
                for cit in frame.provenance.citations:
                    p_str = (
                        f"PDF Page {cit.primary_page}, Doc Page {cit.printed_page}"
                        if cit.printed_page and str(cit.printed_page) != str(cit.primary_page)
                        else f"Page {cit.primary_page}"
                    )
                    head_str = f" — {C.MUTED}{cit.section_heading}{C.RESET}" if cit.section_heading else ""
                    print(f"  • {C.CITATION}[{cit.citation_index}]{C.RESET} {C.CYAN}{cit.document}{C.RESET} ({C.SECTION}{p_str}{C.RESET}){head_str}")
                print()

            TelemetryRenderer.render(frame, session.mode)

            if cli_query is not None:
                break

        except KeyboardInterrupt:
            print(f"\n\n{C.WARN}⚠️  Session interrupted by user.{C.RESET}")
            break
        except Exception as e:
            logger.error(f"Dev studio runtime error: {e}", exc_info=True)
            print(f"\n{C.DANGER}❌ [Error]: {e}{C.RESET}\n")
            if cli_query is not None:
                break
