"""
RAISE TUI — Dedicated Bottom Composer Dock
==========================================
Isolated multi-line input box never corrupted by incoming logs, with mode pill,
command history, bracketed paste, and Nano-style contextual shortcut bar.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static, TextArea

from src.cli.tui.modal_engine import Mode


class ComposerDock(Vertical):
    """Pinned bottom input dock with mode indicator and Nano-style shortcut bar."""

    def __init__(
        self,
        on_submit: Callable[[str], None],
        on_mode_change_request: Optional[Callable[[Mode], None]] = None,
        **kwargs,
    ):
        super().__init__(id="bottom-dock", **kwargs)
        self.submit_callback = on_submit
        self.mode_change_callback = on_mode_change_request
        self.history: List[str] = []
        self.history_index: int = -1

    def compose(self) -> ComposeResult:
        with Horizontal(id="composer-container"):
            yield Static("[NORMAL]", id="mode-pill")
            yield Input(
                placeholder="Type query to run, /command, or press 'i' for insert mode...",
                id="composer-input",
            )
        yield Static(
            "i:Insert  ::Cmd  /:Search  1-5:Tabs  ]e:NextErr  b:Drawer  Ctrl+P:Palette  ?:Help",
            id="shortcut-bar",
        )

    def set_mode_display(self, mode: Mode) -> None:
        pill = self.query_one("#mode-pill", Static)
        pill.remove_class("mode-insert")
        pill.remove_class("mode-command")
        pill.remove_class("mode-search")

        if mode == Mode.INSERT:
            pill.update("[INSERT]")
            pill.add_class("mode-insert")
        elif mode == Mode.COMMAND:
            pill.update("[COMMAND]")
            pill.add_class("mode-command")
        elif mode == Mode.SEARCH:
            pill.update("[SEARCH]")
            pill.add_class("mode-search")
        else:
            pill.update("[NORMAL]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        # Add to history
        if not self.history or self.history[-1] != text:
            self.history.append(text)
        self.history_index = len(self.history)

        # Clear input box
        inp = self.query_one("#composer-input", Input)
        inp.value = ""

        # Delegate execution
        self.submit_callback(text)

    def history_up(self) -> None:
        if not self.history:
            return
        if self.history_index > 0:
            self.history_index -= 1
            inp = self.query_one("#composer-input", Input)
            inp.value = self.history[self.history_index]

    def history_down(self) -> None:
        if not self.history:
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            inp = self.query_one("#composer-input", Input)
            inp.value = self.history[self.history_index]
        else:
            self.history_index = len(self.history)
            inp = self.query_one("#composer-input", Input)
            inp.value = ""
