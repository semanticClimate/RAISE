"""
Slash Commands Discovery Router
===============================
Component: `src.api.routers.commands`
Architecture: API Router for Slash Commands Discovery
Max Lines: Strictly < 400 lines
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from src.features.commands import get_command_registry

router = APIRouter(tags=["Slash Commands"])


@router.get("/api/commands")
async def list_commands_endpoint(response: Response, include_dev: bool = False):
    response.headers['Cache-Control'] = 'public, max-age=60'
    """Returns available system slash commands and syntax for UI auto-complete (excluding dev-only commands by default)."""
    registry = get_command_registry()
    commands = registry.list_commands(include_dev=include_dev)
    return {
        "status": "success",
        "commands": [
            {
                "name": cmd.name,
                "description": cmd.description,
                "syntax": cmd.syntax,
                "examples": cmd.examples,
                "aliases": cmd.aliases,
                "category": cmd.category,
                "is_dev_only": cmd.is_dev_only,
            }
            for cmd in commands
        ],
    }
