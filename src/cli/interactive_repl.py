"""
RAISE — Master Terminal Interactive REPL
========================================
Interactive user shell supporting dynamic conversational routing,
strict drawer isolation, document ingestion, and GraphRAG multi-hop retrieval.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

from src.cli.commands import sanitize_path
from src.cli.document_manager import (
    get_active_documents_list as _fallback_get_docs,
    ingest_pdf_from_path as _fallback_ingest,
    list_active_documents as _fallback_list_docs,
    remove_document_from_library as _fallback_remove,
)
from src.cli.persona_classifier import extract_conversational_persona
from src.cli.renderer import C
from src.cli.status_dashboard import print_help_menu, print_system_status
from prompts.system_synthesis import clean_repetitive_citations

logger = logging.getLogger("RAISE_REPL")


def _get_active_documents_list(*args, **kwargs):
    m = sys.modules.get("main")
    if m and hasattr(m, "get_active_documents_list"):
        return m.get_active_documents_list(*args, **kwargs)
    return _fallback_get_docs(*args, **kwargs)


def _list_active_documents(*args, **kwargs):
    m = sys.modules.get("main")
    if m and hasattr(m, "list_active_documents"):
        return m.list_active_documents(*args, **kwargs)
    return _fallback_list_docs(*args, **kwargs)


def _ingest_pdf_from_path(*args, **kwargs):
    m = sys.modules.get("main")
    if m and hasattr(m, "ingest_pdf_from_path"):
        return m.ingest_pdf_from_path(*args, **kwargs)
    return _fallback_ingest(*args, **kwargs)


def _remove_document_from_library(*args, **kwargs):
    m = sys.modules.get("main")
    if m and hasattr(m, "remove_document_from_library"):
        return m.remove_document_from_library(*args, **kwargs)
    return _fallback_remove(*args, **kwargs)


def run_interactive_studio(
    pipeline: Any,
    memory: Any,
    focused_document: Optional[str] = None,
    user_persona_name: Optional[str] = None,
    cli_query: Optional[str] = None,
) -> None:
    """Executes the standard interactive user console turn loop."""
    active_docs = pipeline.vector_engine.get_active_workspace_documents()

    if not active_docs:
        print(f"\n{C.WARN}⚠️   [NO DOCUMENTS ATTACHED]{C.RESET}")
        print("  Your database currently contains 0 reports.")
        print(f"  Type '{C.ACCENT}upload{C.RESET}' to paste a PDF path and ingest your first report.\n")
    elif focused_document:
        print(f"\n🎯 [{C.MUTED}Active Scope{C.RESET}]: '{C.ACCENT}{focused_document}{C.RESET}' {C.MUTED}(Attached to drawer){C.RESET}")
        print(f"   {C.MUTED}Type '{C.ACCENT}attach all{C.MUTED}' to search all documents, or '{C.ACCENT}library{C.MUTED}' ('{C.ACCENT}docs{C.MUTED}') to view library.{C.RESET}\n")

    while True:
        try:
            scope_badge = f"{focused_document}" if focused_document else "ALL DOCUMENTS"
            prompt_label = f"🔍 [{C.ACCENT}{scope_badge}{C.RESET}] Enter Question: "
            if cli_query is not None:
                query = cli_query.strip()
                print(f"{prompt_label}{query}")
            else:
                try:
                    query = input(prompt_label).strip()
                except EOFError:
                    print(f"\n{C.CYAN}Exiting RAISE Studio. Goodbye!{C.RESET}")
                    break

            if not query:
                if cli_query is not None:
                    break
                continue

            q_lower = query.lower()

            if q_lower in ["exit", "quit", "q", ":q"]:
                print(f"\n{C.CYAN}Exiting RAISE Studio. Goodbye!{C.RESET}")
                break

            if q_lower in ["help", "?", "commands"]:
                print_help_menu()
                if cli_query is not None:
                    break
                continue

            if q_lower in ["status", "health", "info", "diag"]:
                print_system_status(pipeline, memory)
                if cli_query is not None:
                    break
                continue

            if q_lower in ["docs", "list", "documents", "vault", "library"]:
                _list_active_documents(focused_document)
                if cli_query is not None:
                    break
                continue

            if q_lower in ["clear chat", "clear history", "clear memory", "cls"]:
                pipeline.clear_chat_session()
                memory.clear()
                user_persona_name = None
                print(f"\n{C.SUCCESS}✨ [CHAT & MEMORY CLEARED]{C.RESET} Active session context and persona reset.\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["purge all", "wipe all"]:
                print(f"\n{C.DANGER}⛔ [Permission Denied]: System hard purge ('purge all') is not available in user CLI.{C.RESET}")
                print(f"   {C.MUTED}Database purge operations are exclusively restricted to developer tools ('dev_main.py').{C.RESET}\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["delete all", "clear workspace", "reset workspace"]:
                confirm = input(
                    f"{C.WARN}⚠️  Clear custom workspace? This removes your custom uploads and resets chat memory while preserving institutional reports. (y/n): {C.RESET}"
                ).strip().lower()
                if confirm in ["y", "yes"]:
                    from src.cli.document_manager import _resolve_base_dir
                    root = _resolve_base_dir()
                    manifest_file = root / "data" / "processed" / "ingested_manifest.json"
                    user_docs_to_remove = []
                    if manifest_file.exists():
                        try:
                            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                            for d in manifest.get("ready_documents", []):
                                if not d.get("is_protected", False):
                                    user_docs_to_remove.append(d.get("filename"))
                        except Exception:
                            pass

                    removed_count = 0
                    for u_doc in user_docs_to_remove:
                        try:
                            pipeline.purge_document(u_doc)
                            removed_count += 1
                        except Exception:
                            pass

                    pipeline.clear_chat_session()
                    memory.clear()
                    user_persona_name = None

                    remaining = pipeline.vector_engine.get_active_workspace_documents()
                    focused_document = remaining[-1] if remaining else None

                    print(f"\n{C.SUCCESS}✨ [SAFE WORKSPACE RESET COMPLETE]{C.RESET}")
                    print(f"   • {C.MUTED}User uploads removed:{C.RESET} {C.NUM}{removed_count}{C.RESET}")
                    print(f"   • {C.MUTED}Chat memory & persona context reset.{C.RESET}")
                    print(f"   • {C.MUTED}Institutional databases and pre-burned reports remain 100% intact.{C.RESET}\n")
                else:
                    print(f"   {C.MUTED}Workspace reset cancelled.{C.RESET}\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["attach all", "use all", "focus all", "select all", "scope all"]:
                focused_document = None
                print(f"🎯 [{C.SUCCESS}Scope Updated{C.RESET}]: Now searching across {C.ACCENT}ALL documents{C.RESET} simultaneously.\n")
                if cli_query is not None:
                    break
                continue

            if q_lower in ["detach", "attach none", "detach all", "clear drawer"]:
                focused_document = "NONE"
                print(f"🎯 [{C.WARN}Drawer Emptied{C.RESET}]: No documents are currently attached to your drawer.\n")
                if cli_query is not None:
                    break
                continue

            if q_lower.startswith("attach ") or q_lower.startswith("use ") or q_lower.startswith("focus "):
                target = query.split(None, 1)[1].strip().strip("'\"")
                docs = _get_active_documents_list()
                resolved = None
                if target.isdigit():
                    idx = int(target) - 1
                    if 0 <= idx < len(docs):
                        resolved = docs[idx].get("filename")
                else:
                    for d in docs:
                        if target.lower() in d.get("filename", "").lower():
                            resolved = d.get("filename")
                            break
                if resolved:
                    focused_document = resolved
                    print(f"🎯 [{C.SUCCESS}Active Document Attached{C.RESET}]: '{C.ACCENT}{focused_document}{C.RESET}'\n")
                else:
                    print(f"{C.DANGER}❌ Could not match '{target}' to any active document. Type 'docs' to see list.{C.RESET}\n")
                if cli_query is not None:
                    break
                continue

            if q_lower.startswith("delete ") or q_lower.startswith("remove "):
                target = query.split(None, 1)[1].strip().strip("'\"")
                removed = _remove_document_from_library(target, pipeline)
                if removed and focused_document and removed.lower() == focused_document.lower():
                    remaining = pipeline.vector_engine.get_active_workspace_documents()
                    focused_document = remaining[-1] if remaining else None
                    if focused_document:
                        print(f"🎯 {C.SUCCESS}Active focus switched to{C.RESET} '{C.ACCENT}{focused_document}{C.RESET}'.\n")
                    else:
                        print(f"🎯 {C.SUCCESS}Active focus reset to{C.RESET} {C.ACCENT}ALL DOCUMENTS{C.RESET} (library empty).\n")
                if cli_query is not None:
                    break
                continue

            clean_q = query.strip().strip("'\"")
            if clean_q.lower() in ["upload", "add", "ingest"]:
                pdf_input = input(f"📁 {C.SECTION}Enter or paste full PDF file path:{C.RESET} ").strip()
                if pdf_input:
                    new_doc = _ingest_pdf_from_path(pdf_input, pipeline)
                    if new_doc:
                        focused_document = new_doc
                if cli_query is not None:
                    break
                continue

            if clean_q.lower().startswith("upload ") or clean_q.lower().startswith("add ") or clean_q.lower().startswith("ingest "):
                raw_arg = clean_q.split(None, 1)[1].strip()
                m_eng = re.search(r"\b(fast|deep)\b", raw_arg, re.IGNORECASE)
                eng_val = m_eng.group(1).lower() if m_eng else None
                clean_target = re.sub(r"\b(fast|deep)\b", "", raw_arg, flags=re.IGNORECASE).strip().strip("'\"")
                new_doc = _ingest_pdf_from_path(clean_target, pipeline, engine=eng_val)
                if new_doc:
                    focused_document = new_doc
                if cli_query is not None:
                    break
                continue

            if clean_q.lower().endswith(".pdf") or (Path(clean_q).exists() and Path(clean_q).is_file()):
                print(f"\n{C.INFO}[Detected PDF File Path: '{C.WHITE}{sanitize_path(clean_q)}{C.INFO}']{C.RESET}")
                try:
                    confirm = input(f"{C.SECTION}Would you like to ingest this PDF into the research library? (y/n):{C.RESET} ").strip().lower()
                except (EOFError, Exception):
                    confirm = "y"
                if confirm in ["y", "yes", ""]:
                    new_doc = _ingest_pdf_from_path(clean_q, pipeline)
                    if new_doc:
                        focused_document = new_doc
                    if cli_query is not None:
                        break
                    continue

            # Conversational Persona Intent Routing
            intent = extract_conversational_persona(query)
            if intent["type"] == "name_intro":
                prev_name = user_persona_name
                user_persona_name = intent["name"]
                if prev_name and prev_name.lower() != user_persona_name.lower():
                    print(f"\n{C.TITLE}RAISE:{C.RESET} Got it! I've updated your name from {C.BOLD}{prev_name}{C.RESET} to {C.BOLD}{user_persona_name}{C.RESET}. How can I assist you today, {user_persona_name}?\n")
                else:
                    print(f"\n{C.TITLE}RAISE:{C.RESET} Hello {C.BOLD}{user_persona_name}{C.RESET}! My name is {C.ACCENT}RAISE{C.RESET}. I'm here to help you with your research. How can I assist you today?\n")
                if cli_query is not None:
                    break
                continue

            elif intent["type"] == "name_recall":
                if user_persona_name:
                    print(f"\n{C.TITLE}RAISE:{C.RESET} Yes, I do know your name. It's {C.BOLD}{user_persona_name}{C.RESET}. How can I assist you today, {user_persona_name}?\n")
                else:
                    print(f"\n{C.TITLE}RAISE:{C.RESET} You haven't introduced yourself yet! What is your name? (e.g., Sid)\n")
                if cli_query is not None:
                    break
                continue

            elif intent["type"] == "bot_identity":
                if "change" in query.lower():
                    print(f"\n{C.TITLE}RAISE:{C.RESET} My name is fixed as {C.ACCENT}RAISE{C.RESET}, your research intelligence assistant. However, you can change your name anytime by saying 'call me <name>' or 'change my name to <name>'!\n")
                else:
                    print(f"\n{C.TITLE}RAISE:{C.RESET} My name is {C.ACCENT}RAISE{C.RESET}. I'm here to help you with your research. How can I assist you today?\n")
                if cli_query is not None:
                    break
                continue

            elif intent["type"] == "greeting":
                greet_suffix = f", {user_persona_name}" if user_persona_name else ""
                print(f"\n{C.TITLE}RAISE:{C.RESET} Hello{greet_suffix}! I am {C.ACCENT}RAISE{C.RESET}, your research intelligence assistant. Please attach a document in your drawer to begin research.\n")
                if cli_query is not None:
                    break
                continue

            # Factual Query Boundary
            manifest_docs = _get_active_documents_list()
            if not manifest_docs or focused_document == "NONE":
                print(f"\n{C.WARN}⚠️  No active documents are currently attached to your drawer.{C.RESET}")
                print("   Please attach a document in your drawer to begin research.\n")
                if cli_query is not None:
                    break
                continue

            t0 = time.time()
            active_scoping = [focused_document] if focused_document else None
            scope_desc = f"'{focused_document}'" if focused_document else "All Documents"
            print(f"\n{C.INFO}[LangGraph Executing Multi-Hop Retrieval (Target Scope: {C.ACCENT}{scope_desc}{C.INFO})...]{C.RESET}")

            prior_strat = memory.find_similar_strategy(query)
            if prior_strat:
                print(f"  🧠 {C.MAGENTA}Recalled Reasoning Trajectory{C.RESET} ({C.ACCENT}{prior_strat.trajectory_id}{C.RESET}) {C.MUTED}with confidence {prior_strat.confidence_score}{C.RESET}")

            # Expand top_k on roster / entity queries or when prior trajectory recalled to prevent lock-in
            is_roster_or_detail = any(w in query.lower() for w in ["name", "names", "list", "member", "members", "invitee", "invitees", "who", "all"])
            effective_k = 15 if (is_roster_or_detail or prior_strat) else 8

            res = pipeline.query_subgraph_graphrag(
                query=query,
                hops=2,
                top_k=effective_k,
                document_filter=focused_document,
                active_docs=active_scoping,
            )
            elapsed = round(time.time() - t0, 2)

            if not isinstance(res, dict):
                res = {"grounded_answer": str(res)}

            traceability = res.get("traceability_score", 0.85) if isinstance(res, dict) else 0.85
            answer = res.get("grounded_answer", "No response generated.") if isinstance(res, dict) else str(res)
            if isinstance(answer, str):
                answer = clean_repetitive_citations(answer)

            print("\n" + C.BANNER + "═" * 74 + C.RESET)
            print(f" {C.TITLE}📋 GROUNDED RESEARCH ANSWER{C.RESET} {C.MUTED}({elapsed}s | Traceability: {traceability}){C.RESET}")
            print(f" {C.MUTED}📄 Attached Document:{C.RESET} {C.ACCENT}{scope_desc}{C.RESET}")
            print(C.BANNER + "═" * 74 + C.RESET)

            colorized_answer = re.sub(
                r"\[(\d+(?:,\s*\d+)*)\]",
                lambda m: f"{C.CITATION}[{m.group(1)}]{C.RESET}",
                answer,
            )
            print(colorized_answer)

            # Display Verified Citations
            try:
                citations = res.get("citations") or [] if isinstance(res, dict) else []
                if citations:
                    cited_indices = set()
                    if isinstance(answer, str):
                        try:
                            cited_indices = set(int(m) for m in re.findall(r"\[(\d+)\]", answer))
                        except Exception:
                            cited_indices = set()
                    active_cits = [c for c in citations if isinstance(c, dict) and c.get("citation_index") in cited_indices] if cited_indices else (citations[:2] if citations else [])
                    if active_cits:
                        print(f"\n{C.SECTION}📚 Verified Source Citations:{C.RESET}")
                        for c in active_cits:
                            if isinstance(c, dict):
                                c_idx = c.get("citation_index", "?")
                                c_pdf = c.get("pdf_filename", "Unknown PDF")
                                c_page = c.get("primary_page", "N/A")
                                doc_p = c.get("printed_page")
                                c_head = c.get("heading", "")
                                if doc_p and str(doc_p).strip() != "" and str(doc_p) != str(c_page):
                                    page_str = f"PDF Page {c_page}, Doc Page {doc_p}"
                                else:
                                    page_str = f"Page {c_page}"
                                head_str = f" — {C.MUTED}{c_head}{C.RESET}" if c_head else ""
                                p_url = c.get("page_url")
                                url_hint = f"\n    {C.MUTED}↳ View Page: {C.CYAN}http://localhost:8000{p_url}{C.RESET}" if p_url else ""
                                print(f"  • {C.CITATION}[{c_idx}]{C.RESET} {C.WHITE}{c_pdf}{C.RESET} ({C.SECTION}{page_str}{C.RESET}){head_str}{url_hint}")
            except Exception as cit_err:
                logger.warning(f"Citation rendering notice: {cit_err}")

            # Display Connected Neo4j Subgraph Entities
            try:
                subgraph = res.get("subgraph") or {} if isinstance(res, dict) else {}
                nodes = subgraph.get("nodes") or [] if isinstance(subgraph, dict) else []
                if nodes:
                    print(f"\n{C.ENTITY}🕸️  Connected Neo4j Subgraph Entities ({len(nodes)} nodes):{C.RESET}")
                    for n in nodes[:8]:
                        if isinstance(n, dict):
                            lbl = n.get("type") or n.get("label") or "Entity"
                            val = n.get("name") or n.get("id") or ""
                            print(f"  • {C.CYAN}({lbl}){C.RESET}: {C.NUM}{val}{C.RESET}")
            except Exception as sub_err:
                logger.warning(f"Subgraph rendering notice: {sub_err}")

            # Record trajectory in Reasoning Memory
            try:
                tools_used = res.get("selected_tools") if (isinstance(res, dict) and res.get("selected_tools")) else ["vector_search", "graph_traversal", "claim_verifier"]
                is_grounded = res.get("grounded", True) if isinstance(res, dict) else True
                memory.record_trajectory(
                    query=query,
                    tools_used=tools_used,
                    resolved_entities={},
                    metrics=[],
                    confidence=traceability,
                    passed=is_grounded,
                )
            except Exception as mem_err:
                logger.warning(f"Memory recording notice: {mem_err}")

            print(C.MUTED + "─" * 74 + C.RESET + "\n")

            if cli_query is not None:
                break

        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.CYAN}Exiting RAISE Studio. Goodbye!{C.RESET}")
            break
        except Exception as e:
            print(f"\n{C.DANGER}[Error executing query]: {sanitize_path(str(e))}{C.RESET}\n")
            if cli_query is not None:
                break
