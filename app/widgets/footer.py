from textual.widgets import Static

class CustomFooter(Static):
    """Footer with metadata."""
    def render(self) -> str:
        state = self.app.state if hasattr(self.app, 'state') else None
        if state:
            thinking_label = "thinking" if state.thinking_mode else "normal"
            return f"Workspace: {state.workspace} | Mode: {state.mode} | Thinking: {thinking_label} [Ctrl+T] "
        return "Workspace: . | Mode: permission | Thinking: thinking [Ctrl+T] "