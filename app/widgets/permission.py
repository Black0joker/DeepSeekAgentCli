from textual.widgets import ListView, ListItem
from textual.message import Message
from textual.widgets import Static

class PermissionSelector(ListView):
    """A ListView that presents permission options: Allow once, Allow for session, Reject."""
    
    class Selected(Message):
        """Posted when an option is selected."""
        def __init__(self, decision: str):
            self.decision = decision
            super().__init__()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._populated = False

    def on_mount(self):
        """Populate the list when the widget is mounted."""
        self._populate()

    def _populate(self):
        """Populate the list with the three permission options."""
        if self._populated:
            return
        options = [
            ("Allow once", "allow_once"),
            ("Allow for session", "allow_session"),
            ("Reject", "reject")
        ]
        for label, value in options:
            item = ListItem(Static(label))
            item.decision = value
            self.append(item)
        self._populated = True
    
    def action_select_cursor(self) -> None:
        """Override default action to post our custom message with only the decision."""
        selected_child = self.highlighted_child
        if selected_child is None:
            return
        decision = selected_child.decision
        self.post_message(self.Selected(decision))
