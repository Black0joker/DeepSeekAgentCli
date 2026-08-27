from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class AppState:
    """Application state container for UI metadata."""
    model: str = "DeepSeek-V3"
    workspace: str = "."
    branch: str = "main"
    settings: dict = field(default_factory=dict)
    mode: str = "auto"  # "auto" or "permission"
    thinking_mode: bool = True  # "thinking" or "normal"

    def set_model(self, model: str) -> None:
        """Change the current model."""
        self.model = model

    def set_workspace(self, path: str) -> None:
        """Set workspace directory."""
        self.workspace = path

    def set_branch(self, branch: str) -> None:
        """Set git branch."""
        self.branch = branch

    def set_mode(self, mode: str) -> None:
        """Set the operation mode: 'auto' or 'permission'."""
        if mode in ("auto", "permission"):
            self.mode = mode
        else:
            raise ValueError("Mode must be 'auto' or 'permission'")

    def toggle_thinking_mode(self) -> str:
        """Toggle thinking mode between True and False. Returns new mode label."""
        self.thinking_mode = not self.thinking_mode
        return "thinking" if self.thinking_mode else "normal"
