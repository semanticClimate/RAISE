"""
RAISE TUI — Tab 2: Interactive Query & Research Studio
======================================================
Renders user queries, streaming Markdown answers, citations, and execution telemetry.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Markdown as TextualMarkdown, Static


class QueryLiveTab(Vertical):
    """Tab 2: Interactive Research & Query Stream Workbench."""

    def __init__(self, on_inspect: Optional[Callable[[str, Any], None]] = None, **kwargs):
        super().__init__(id="tab-query", classes="tab-pane", **kwargs)
        self.inspect_callback = on_inspect
        self.query_history: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("RESEARCH & QUERY STUDIO (Run queries from the composer below)", id="query-title")
        with VerticalScroll(id="query-scroll"):
            yield Static(
                "Welcome to the RAISE Developer Workbench.\nType your research query in the composer below and press Enter.",
                id="query-welcome",
            )

    def display_query_start(self, query: str) -> None:
        scroll = self.query_one("#query-scroll", VerticalScroll)
        # Remove welcome banner if present
        welcome = self.query("#query-welcome")
        if welcome:
            welcome.first().remove()

        q_block = Static(Text(f"\nQUERY: {query}\n", style="bold #5fd7ff"), classes="query-prompt-block")
        scroll.mount(q_block)
        scroll.scroll_end(animate=False)

    def display_query_result(self, result: Dict[str, Any]) -> None:
        scroll = self.query_one("#query-scroll", VerticalScroll)
        self.query_history.append(result)

        answer = result.get("grounded_answer") or result.get("answer") or "NO_ANSWER"
        citations = result.get("citations") or []
        req_id = result.get("request_id", "req_unknown")
        status = result.get("status", "SUCCESS")

        # Answer Markdown Widget
        ans_widget = TextualMarkdown(answer, classes="query-answer-block")
        scroll.mount(ans_widget)

        # Citations block
        if citations:
            cit_lines = []
            for idx, c in enumerate(citations[:5], 1):
                fn = c.get("pdf_filename") or (c.get("metadata", {}).get("pdf_filename") if isinstance(c, dict) else "Doc")
                page = c.get("primary_page") or (c.get("metadata", {}).get("primary_page") if isinstance(c, dict) else "?")
                cid = c.get("chunk_id") or (c.get("id") if isinstance(c, dict) else "?")
                cit_lines.append(f"  [{idx}] {fn} (Page {page}) - chunk: {cid}")

            cit_text = Text("\nCITATIONS:\n" + "\n".join(cit_lines), style="#87d787")
            scroll.mount(Static(cit_text, classes="query-citations-block"))

        # Execution telemetry badge
        ret_ms = result.get("retrieval_ms", 0.0)
        rer_ms = result.get("rerank_ms", 0.0)
        syn_ms = result.get("synthesis_ms", 0.0)
        total_time = result.get("execution_time", 0.0)
        meta_txt = Text(
            f"─── [{req_id}] status: {status} · total: {total_time}s (ret: {ret_ms}ms · rerank: {rer_ms}ms · synth: {syn_ms}ms) ───\n",
            style="dim",
        )
        scroll.mount(Static(meta_txt))
        scroll.scroll_end(animate=False)
