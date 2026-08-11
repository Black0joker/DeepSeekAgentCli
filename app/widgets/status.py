from textual.widgets import Static
from textual.timer import Timer
from rich.text import Text

class StatusBar(Static):
    """Status line with animated spinner and elapsed timer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_text = "Ready"
        self.spinner_chars = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"]
        self.spinner_index = 0
        self.timer: Timer | None = None
        self.spinner_active = False
        # Elapsed timer attributes
        self.elapsed_active = False
        self.elapsed_seconds = 0
        self.elapsed_timer: Timer | None = None

    def on_mount(self) -> None:
        self.render()

    def render(self) -> Text:
        # Style for status text when it's "Thinking..."
        if self.status_text == "Thinking...":
            status_style = "bold bright_white"
        else:
            status_style = ""

        if self.elapsed_active:
            spinner = self.spinner_chars[self.spinner_index] if self.spinner_active else ""
            # Build status with elapsed seconds
            status_part = Text(self.status_text, style=status_style)
            elapsed_part = Text(f" ({self.elapsed_seconds}s)", style="dim")
            return Text(spinner + " ") + status_part + elapsed_part
        elif self.spinner_active and self.status_text != "Ready":
            spinner = self.spinner_chars[self.spinner_index]
            status_part = Text(self.status_text, style=status_style)
            return Text(spinner + " ") + status_part
        else:
            return Text(self.status_text, style=status_style)

    def set_status(self, text: str) -> None:
        """Update the status text and stop any running timer if status becomes Ready."""
        self.status_text = text
        if text == "Ready":
            self.stop_elapsed_timer()
            self.stop_spinner()
        else:
            self.start_spinner()
        self.refresh()

    def start_elapsed_timer(self, text: str) -> None:
        """Start a stopwatch timer that counts up seconds and displays elapsed time.
        
        Args:
            text: Status text to display (e.g., "Thinking...")
        """
        # Stop any existing timer and spinner
        self.stop_elapsed_timer()
        self.stop_spinner()
        
        self.status_text = text
        self.elapsed_seconds = 1
        self.elapsed_active = True
        self.start_spinner()
        
        # Start the timer that increments every second
        self.elapsed_timer = self.set_interval(1.0, self._update_elapsed)
        self.refresh()

    def _update_elapsed(self) -> None:
        """Increment elapsed seconds and refresh the display."""
        if not self.elapsed_active:
            return
        self.elapsed_seconds += 1
        self.refresh()

    def stop_elapsed_timer(self) -> None:
        """Stop the elapsed timer and reset state."""
        if self.elapsed_timer:
            self.elapsed_timer.stop()
            self.elapsed_timer = None
        self.elapsed_active = False
        self.elapsed_seconds = 0
        self.refresh()

    def start_spinner(self) -> None:
        """Start the spinner animation if not already running."""
        if not self.spinner_active:
            self.spinner_active = True
            self.timer = self.set_interval(0.1, self.advance_spinner)

    def stop_spinner(self) -> None:
        """Stop the spinner animation."""
        if self.spinner_active:
            self.spinner_active = False
            if self.timer:
                self.timer.stop()
                self.timer = None

    def advance_spinner(self) -> None:
        """Advance to the next spinner character and refresh."""
        if self.spinner_active:
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
            self.refresh()

    def on_unmount(self) -> None:
        """Stop all timers when widget is unmounted."""
        self.stop_spinner()
        self.stop_elapsed_timer()
