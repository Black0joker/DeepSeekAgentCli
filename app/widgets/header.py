from textual.widgets import Static

class CustomHeader(Static):
    """Custom header widget."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = "Ready"

    def render(self) -> str:
        return f"◆ {self.state}"

    def set_state(self, state: str) -> None:
        self.state = state
        self.refresh()
