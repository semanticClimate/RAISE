"""
RAISE TUI — Vim-Inspired Modal Engine & Keybinding Dispatcher
============================================================
Decoupled modal manager supporting NORMAL, INSERT, COMMAND, and SEARCH modes.
"""

from __future__ import annotations

from enum import Enum
import subprocess
from typing import Callable, List, Optional


class Mode(str, Enum):
    NORMAL = "NORMAL"
    INSERT = "INSERT"
    COMMAND = "COMMAND"
    SEARCH = "SEARCH"


class ModeManager:
    def __init__(self, on_mode_change: Optional[Callable[[Mode], None]] = None):
        self.current_mode = Mode.NORMAL
        self.on_mode_change = on_mode_change
        self.key_buffer: List[str] = []

    def set_mode(self, new_mode: Mode) -> None:
        if self.current_mode != new_mode:
            self.current_mode = new_mode
            self.key_buffer.clear()
            if self.on_mode_change:
                self.on_mode_change(new_mode)

    @property
    def is_insert(self) -> bool:
        return self.current_mode == Mode.INSERT

    @property
    def is_normal(self) -> bool:
        return self.current_mode == Mode.NORMAL

    @property
    def is_command(self) -> bool:
        return self.current_mode == Mode.COMMAND

    @property
    def is_search(self) -> bool:
        return self.current_mode == Mode.SEARCH


def copy_to_clipboard(text: str) -> bool:
    """Copies text to the Windows system clipboard via clip.exe or PowerShell."""
    if not text:
        return False
    try:
        proc = subprocess.Popen(["clip.exe"], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.communicate(input=text.encode("utf-8"))
        return proc.returncode == 0
    except Exception:
        try:
            cmd = f"Set-Clipboard -Value @'\n{text}\n'@"
            subprocess.run(["powershell.exe", "-Command", cmd], capture_output=True, timeout=2)
            return True
        except Exception:
            return False
