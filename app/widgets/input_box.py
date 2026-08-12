from textual.widgets import Input
from textual import events
from textual.message import Message
from typing import Any, cast

from app.widgets.suggestions import SuggestionsList

class InputBox(Input):
    class MessageSent(Message):
        def __init__(self, text: str):
            self.text = text
            super().__init__()

    class TextChanged(Message):
        def __init__(self, text: str):
            self.text = text
            super().__init__()

    class SuggestionSelected(Message):
        def __init__(self, text: str):
            self.text = text
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Type your message or /command"
        self.history: list[str] = []
        self.history_index: int = -1
        self._current_draft: str = ""

    @property
    def text(self) -> str:
        return self.value

    @text.setter
    def text(self, val: str) -> None:
        self.value = val

    def on_key(self, event: events.Key) -> None:
        suggestions = self.app.suggestions if hasattr(self.app, "suggestions") else None
        suggestions = cast(SuggestionsList, suggestions)

        if suggestions and suggestions.display:
            if event.key == "up":
                suggestions.move_up()
                event.prevent_default()
                return
            elif event.key == "down":
                suggestions.move_down()
                event.prevent_default()
                return
            elif event.key in ("enter", "tab"):
                value = suggestions.get_selected_value()
                if value:
                    self.apply_suggestion(value)
                suggestions.close()
                event.prevent_default()
                text = self.text
                if text.startswith("/"):
                    parts = text.split()
                    cmd_name = parts[0] if parts else ""
                    requires_args = self.app.command_requires_args(cmd_name) if hasattr(self.app, "command_requires_args") else False
                    if requires_args:
                        self.cursor_position = len(self.text)
                        self.refresh()
                        self.focus()
                    else:
                        self.text = ""
                        self.post_message(self.MessageSent(text.strip()))
                else:
                    self.text = ""
                    self.post_message(self.MessageSent(text.strip()))
                return
            elif event.key == "escape":
                suggestions.close()
                event.prevent_default()
                return

        # Input history navigation (Up/Down when no suggestions visible)
        if event.key == "up" and not (suggestions and suggestions.display):
            if self.history:
                if self.history_index == -1:
                    # Save current draft before navigating
                    self._current_draft = self.text
                    self.history_index = len(self.history) - 1
                elif self.history_index > 0:
                    self.history_index -= 1
                self.text = self.history[self.history_index]
                self.cursor_position = len(self.text)
            event.prevent_default()
            return
        elif event.key == "down" and not (suggestions and suggestions.display):
            if self.history and self.history_index >= 0:
                if self.history_index < len(self.history) - 1:
                    self.history_index += 1
                    self.text = self.history[self.history_index]
                else:
                    # Back to the original draft
                    self.history_index = -1
                    self.text = self._current_draft
                self.cursor_position = len(self.text)
            event.prevent_default()
            return

        if event.key == "enter":
            text = self.text
            if text.strip():
                # Add to history (avoid consecutive duplicates)
                if not self.history or self.history[-1] != text.strip():
                    self.history.append(text.strip())
                    # Keep history bounded to last 100 entries
                    if len(self.history) > 100:
                        self.history = self.history[-100:]
                self.history_index = -1
                self._current_draft = ""
                self.text = ""
                self.post_message(self.MessageSent(text.strip()))
            event.prevent_default()
            return
        elif event.key == "shift+enter":
            # Insert newline at cursor position
            current = self.text
            pos = self.cursor_position
            self.text = current[:pos] + "\n" + current[pos:]
            self.cursor_position = pos + 1
            event.prevent_default()
            return

        self.call_after_refresh(self._emit_text_changed)

    def _emit_text_changed(self):
        self.post_message(self.TextChanged(self.text))

    def apply_suggestion(self, suggestion: str) -> None:
        current = self.text
        if current.startswith("/"):
            space_idx = current.find(" ")
            if space_idx == -1:
                self.text = suggestion
            else:
                args = current[space_idx:]
                self.text = suggestion + args
        else:
            self.text = suggestion
        self.cursor_position = len(self.text)
        self.refresh()
