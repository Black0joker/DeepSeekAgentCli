from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Set

@dataclass
class AppState:
    """Application state container for UI metadata."""
    model: str = "DeepSeek-V3"
    workspace: str = "."
    branch: str = "main"
    settings: dict = field(default_factory=dict)
    mode: str = "auto"  # "auto" or "permission"
    allowed_tools_session: Set[str] = field(default_factory=set)
    allowed_tools_once: Set[str] = field(default_factory=set)

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

    def clear_allowed_tools(self) -> None:
        """Clear all session and once permission caches."""
        self.allowed_tools_session.clear()
        self.allowed_tools_once.clear()
