from textual.widgets import ListView, ListItem
from textual import events
from textual.message import Message
from textual.widgets import Static
from app.theme import ACCENT_RGB
from rich.text import Text


class PermissionSelector(ListView):
    """A ListView that presents permission options: Allow once, Allow for session, Reject.
    
    Supports keyboard shortcuts: y = allow once, s = allow session, n = reject.
    """
    
    class Selected(Message):
        """Posted when an option is selected."""
        def __init__(self, decision: str):
            self.decision = decision
            super().__init__()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._populated = False
        self._tool_label: str = ""

    def set_tool_info(self, tool: str, args: dict) -> None:
        """Set the tool information to display in the selector header."""
        self._tool_label = f"Tool: {tool} with args: {args}"

    def on_mount(self):
        """Populate the list when the widget is mounted."""
        self._populate()

    def _populate(self):
        """Populate the list with the three permission options."""
        if self._populated:
            return
        options = [
            ("[y] Allow once", "allow_once"),
            ("[s] Allow for session", "allow_session"),
            ("[n] Reject", "reject"),
        ]
        for label, value in options:
            item = ListItem(Static(label))
            item.decision = value
            self.append(item)
        self._populated = True

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts for permission decisions."""
        key = event.key.lower()
        if key == "y":
            self.post_message(self.Selected("allow_once"))
            event.prevent_default()
        elif key == "s":
            self.post_message(self.Selected("allow_session"))
            event.prevent_default()
        elif key == "n":
            self.post_message(self.Selected("reject"))
            event.prevent_default()
        elif key == "escape":
            self.post_message(self.Selected("reject"))
            event.prevent_default()

    def action_select_cursor(self) -> None:
        """Override default action to post our custom message with only the decision."""
        selected_child = self.highlighted_child
        if selected_child is None:
            return
        decision = selected_child.decision
        self.post_message(self.Selected(decision))
