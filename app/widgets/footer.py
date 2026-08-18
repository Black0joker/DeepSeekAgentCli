"""Footer with session metadata: workspace, mode, thinking, git branch, theme."""
from textual.widgets import Static

from app.agent.logger import Logger


class CustomFooter(Static):
    """Footer with metadata."""

    def on_mount(self) -> None:
        self._cached_branch: str | None = None

    def _detect_git_branch(self, workspace: str) -> str | None:
        """Detect the current git branch for a workspace (cached)."""
        import subprocess
        import os
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=workspace,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            Logger.debug(f"Git branch detection failed in {workspace}: {e}")
        return None

    def render(self) -> str:
        state = self.app.state if hasattr(self.app, 'state') else None
        if state:
            thinking_label = "thinking" if state.thinking_mode else "normal"

            # Shorten workspace path for display
            workspace = state.workspace
            if len(workspace) > 40:
                parts = workspace.replace("\\", "/").split("/")
                if len(parts) > 2:
                    workspace = f".../{'/'.join(parts[-2:])}"

            # Git branch detection (only check once per workspace change)
            branch = None
            if hasattr(self, "_cached_workspace") and self._cached_workspace == workspace:
                branch = getattr(self, "_cached_branch", None)
            else:
                self._cached_workspace = workspace
                branch = self._detect_git_branch(state.workspace)
                self._cached_branch = branch

            parts = [
                f"[dim]ws:[/dim] [bold]{workspace}[/bold]",
            ]
            if branch:
                parts.append(f"[dim]git:[/dim] [bold]#{branch}[/bold]")
            parts.append(f"[dim]mode:[/dim] [bold]{state.mode}[/bold]")
            parts.append(f"[dim]thinking:[/dim] [bold]{thinking_label}[/bold]")
            return "  │  ".join(parts)
        return "DeepSeekCli"
