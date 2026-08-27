"""In-place tool call entry for the conversation view.

Instead of writing two separate lines (before + after), a single widget is
mounted when the agent starts a tool call:

  1. RUNNING state  - animated braille spinner + tool name + arguments,
                      with an accent-colored left bar.
  2. COMPLETED      - the widget updates itself in place with the result
                      summary, optional dim detail block (command output,
                      diff excerpt, grep hits), elapsed duration, and a
                      green/red left bar depending on success/error.

This keeps the conversation compact and gives live feedback while tools run.
"""

from __future__ import annotations

import time
from typing import Optional

from rich.text import Text
from textual.widgets import Static

from app.widgets.tool_writer import format_tool_running, format_tool_done


_SPINNER_FRAMES = [
    "\u280B", "\u2819", "\u2839", "\u2838", "\u283C",
    "\u2834", "\u2826", "\u2827", "\u2807", "\u280F",
]
_SPINNER_INTERVAL = 0.12


class ToolCallEntry(Static):
    """A single conversation entry representing one tool invocation."""

    # Colors come from CSS variables provided by the active Textual theme.
    DEFAULT_CSS = """
    ToolCallEntry {
        height: auto;
        margin: 1 1 1 2;
        padding: 0 1;
        border-left: thick $accent;
    }
    ToolCallEntry.success {
        border-left: thick $success;
    }
    ToolCallEntry.error {
        border-left: thick $error;
    }
    """

    def __init__(self, tool: str, args: dict, call_id: Optional[str] = None, **kwargs):
        self.tool = tool
        self.args = args
        self.call_id = call_id
        self._start = time.monotonic()
        self._frame = 0
        self._done = False
        self._timer = None
        # Pass the initial running-state renderable through the Static
        # constructor (safe without an active app); live updates happen
        # only after mount.
        super().__init__(format_tool_running(tool, args), **kwargs)

    def on_mount(self) -> None:
        self._timer = self.set_interval(_SPINNER_INTERVAL, self._tick)

    def _tick(self) -> None:
        if self._done:
            return
        self._frame = (self._frame + 1) % len(_SPINNER_FRAMES)
        self._render_running()

    def _render_running(self) -> None:
        frame = _SPINNER_FRAMES[self._frame]
        self.update(format_tool_running(self.tool, self.args, spinner=frame))

    def complete(self, result: dict) -> None:
        """Transition the entry to its final state with the tool result."""
        if self._done:
            return
        self._done = True
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

        duration = time.monotonic() - self._start
        main, detail = format_tool_done(self.tool, self.args, result, duration)

        if detail is not None:
            main.append("\n")
            main.append_text(detail)

        self.update(main)

        if result.get("status") == "error":
            self.add_class("error")
        else:
            self.add_class("success")
