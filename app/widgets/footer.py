from textual.widgets import Static

class CustomFooter(Static):
    """Footer with metadata."""
    def render(self) -> str:
        state = self.app.state if hasattr(self.app, 'state') else None
        if state:
            return f"Workspace: {state.workspace} | Branch: {state.branch} | Model: {state.model} | Mode: {state.mode} "
        return "Workspace: . | Branch: main | Model: DeepSeek-V3 | Mode: permission "