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
        self.placeholder = "Type your message or @path/to/file"

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

        if event.key == "enter":
            text = self.text
            if text.strip():
                self.text = ""
                self.post_message(self.MessageSent(text.strip()))
            event.prevent_default()
            return
        elif event.key == "shift+enter":
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
