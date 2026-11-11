"""
Modular Command Registry & Dispatcher
======================================
Component: `src.features.commands.registry`
Architecture: Pluggable Slash Command System for RAISE
Max Lines: Strictly < 400 lines
"""

from __future__ import annotations

import logging
import shlex
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import CommandContext, CommandMetadata, CommandResult

logger = logging.getLogger("raise.commands.registry")

CommandHandler = Callable[[CommandContext], CommandResult]


class CommandRegistry:
    """Central registry and execution dispatcher for all system slash commands."""

    def __init__(self) -> None:
        self._handlers: Dict[str, CommandHandler] = {}
        self._metadata: Dict[str, CommandMetadata] = {}
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        name: str,
        description: str,
        syntax: str,
        examples: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        category: str = "General",
        is_dev_only: bool = False,
    ) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register a function as a slash command."""
        cmd_name = name.lower().lstrip("/")

        def decorator(func: CommandHandler) -> CommandHandler:
            self._handlers[cmd_name] = func
            meta = CommandMetadata(
                name=f"/{cmd_name}",
                description=description,
                syntax=syntax,
                examples=examples or [],
                aliases=[f"/{a.lstrip('/')}" for a in (aliases or [])],
                category=category,
                is_dev_only=is_dev_only,
            )
            self._metadata[cmd_name] = meta
            if aliases:
                for a in aliases:
                    self._aliases[a.lower().lstrip("/")] = cmd_name
            logger.info("Registered slash command: /%s [%s] (dev_only=%s)", cmd_name, category, is_dev_only)
            return func

        return decorator

    def get_handler(self, command_name: str) -> Optional[CommandHandler]:
        """Resolves a command handler by primary name or registered alias."""
        clean = command_name.lower().lstrip("/")
        primary = self._aliases.get(clean, clean)
        return self._handlers.get(primary)

    def get_metadata(self, command_name: str) -> Optional[CommandMetadata]:
        """Retrieves help and schema metadata for a command."""
        clean = command_name.lower().lstrip("/")
        primary = self._aliases.get(clean, clean)
        return self._metadata.get(primary)

    def list_commands(self, include_dev: bool = False) -> List[CommandMetadata]:
        """Returns sorted list of registered commands. By default excludes dev-only commands."""
        cmds = [m for m in self._metadata.values() if include_dev or not m.is_dev_only]
        return sorted(cmds, key=lambda m: m.name)

    @staticmethod
    def parse_command_line(raw_text: str) -> Tuple[Optional[str], str, List[str]]:
        """
        Parses text like '/compare research --docs=A,B' into:
        (command_name: 'compare', raw_args: 'research --docs=A,B', args: ['research', '--docs=A,B'])
        """
        stripped = raw_text.strip()
        if not stripped.startswith("/"):
            return None, stripped, []

        parts = stripped.split(None, 1)
        cmd_name = parts[0][1:].lower()
        raw_args = parts[1].strip() if len(parts) > 1 else ""

        args: List[str] = []
        if raw_args:
            try:
                args = shlex.split(raw_args)
            except Exception:
                args = raw_args.split()

        return cmd_name, raw_args, args

    def dispatch(self, ctx: CommandContext) -> CommandResult:
        """Executes a command by dispatching to its registered handler."""
        handler = self.get_handler(ctx.command_name)
        if not handler:
            return CommandResult(
                status="ERROR",
                command=f"/{ctx.command_name}",
                answer=f"Unknown command `/{ctx.command_name}`. Type `/help` to see all available slash commands.",
                quality_gate_decision="accept",
            )

        t0 = time.perf_counter()
        try:
            result = handler(ctx)
            result.execution_time = round(time.perf_counter() - t0, 3)
            result.command = f"/{ctx.command_name}"
            return result
        except Exception as e:
            logger.exception("Error executing command /%s: %s", ctx.command_name, e)
            return CommandResult(
                status="ERROR",
                command=f"/{ctx.command_name}",
                answer=f"Execution error while running `/{ctx.command_name}`: {str(e)}",
                execution_time=round(time.perf_counter() - t0, 3),
                quality_gate_decision="unable_to_verify",
            )


# Global singleton registry instance
_GLOBAL_REGISTRY: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """Returns the global CommandRegistry singleton."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = CommandRegistry()
    return _GLOBAL_REGISTRY
