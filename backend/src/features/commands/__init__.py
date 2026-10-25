"""
Modular Slash Commands Subsystem for RAISE
==========================================
Component: `src.features.commands`
Architecture: Pluggable Slash Commands Registry and Handlers
Max Lines: Strictly < 400 lines
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .browser_command import handle_browser_command
from .compare_command import handle_compare_command
from .core_commands import (
    handle_audit_command,
    handle_bench_command,
    handle_graph_command,
    handle_help_command,
    handle_synthesize_command,
)
from .pdf_metric_extractor import extract_pdf_institutional_profile
from .registry import CommandRegistry, get_command_registry
from .types import CommandContext, CommandMetadata, CommandResult, ComparabilityStatus
from .web_fetcher import SupplementalWebFetcher


def _init_default_commands(registry: CommandRegistry) -> None:
    """Registers default commands into the global registry."""
    registry.register(
        name="compare",
        description="Side-by-side institutional comparison across 17 operational dimensions.",
        syntax="/compare [focus: research|academics|finance|faculty|sustainability]",
        examples=["/compare", "/compare research", "/compare finance"],
        aliases=["diff", "versus", "vs"],
        category="Comparison",
    )(handle_compare_command)

    registry.register(
        name="audit",
        description="Strict anti-hallucination factual audit with numerical cross-checking.",
        syntax="/audit [claim or section]",
        examples=["/audit", "/audit patents and publications", "/audit budget expenditures"],
        aliases=["verify", "factcheck"],
        category="Verification",
        is_dev_only=True,
    )(handle_audit_command)

    registry.register(
        name="synthesize",
        description="Executive institutional synthesis covering accomplishments, publications, and governance.",
        syntax="/synthesize [focus]",
        examples=["/synthesize", "/synthesize scientific achievements"],
        aliases=["summary", "summarize", "overview"],
        category="Synthesis",
        is_dev_only=True,
    )(handle_synthesize_command)

    registry.register(
        name="graph",
        description="Traverse knowledge graph entity networks, projects, and relationships.",
        syntax="/graph [entity or topic]",
        examples=["/graph", "/graph Early Flowering 3a", "/graph Institutional Collaborations"],
        aliases=["explore", "kg", "network"],
        category="Knowledge Graph",
        is_dev_only=True,
    )(handle_graph_command)

    registry.register(
        name="browser",
        description="Extract supplemental research facts and public data from the internet.",
        syntax="/browser [url or search topic]",
        examples=["/browser NIRF Rankings IIT Madras", "/browser https://en.wikipedia.org/wiki/Harvard_University"],
        aliases=["web", "fetch", "internet"],
        category="Research",
        is_dev_only=False,
    )(handle_browser_command)

    registry.register(
        name="bench",
        description="Run live evaluation across the 8-part industry benchmark suite.",
        syntax="/bench",
        examples=["/bench"],
        aliases=["eval", "benchmark", "scorecard"],
        category="Diagnostics",
        is_dev_only=True,
    )(handle_bench_command)

    registry.register(
        name="help",
        description="Show all available slash commands and usage syntax.",
        syntax="/help",
        examples=["/help"],
        aliases=["commands", "?"],
        category="Help",
        is_dev_only=True,
    )(handle_help_command)


# Initialize default commands upon module load
_init_default_commands(get_command_registry())


def is_slash_command(text: str) -> bool:
    """Checks if a user query text represents a slash command."""
    s = text.strip()
    return s.startswith("/") and len(s) > 1 and not s.startswith("//")


def execute_slash_command(
    raw_query: str,
    active_docs: Optional[List[str]] = None,
    session_id: str = "default",
    request_id: str = "",
    mode: str = "fast",
    stream: bool = False,
    rag_engine: Any = None,
) -> Optional[CommandResult]:
    """Parses and executes a slash command if present in the query."""
    if not is_slash_command(raw_query):
        return None

    registry = get_command_registry()
    cmd_name, raw_args, args = registry.parse_command_line(raw_query)
    if not cmd_name:
        return None

    ctx = CommandContext(
        query=raw_query,
        command_name=cmd_name,
        raw_args=raw_args,
        args=args,
        active_docs=active_docs,
        session_id=session_id,
        request_id=request_id,
        mode=mode,
        stream=stream,
        rag_engine=rag_engine,
    )
    return registry.dispatch(ctx)


__all__ = [
    "CommandContext",
    "CommandMetadata",
    "CommandRegistry",
    "CommandResult",
    "ComparabilityStatus",
    "SupplementalWebFetcher",
    "execute_slash_command",
    "extract_pdf_institutional_profile",
    "get_command_registry",
    "handle_browser_command",
    "is_slash_command",
]
