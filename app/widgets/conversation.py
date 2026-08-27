from textual.widgets import Static
from textual.containers import Container
from rich.text import Text
from rich.markdown import Markdown
from typing import Union
from app.theme import (
    TEXT_PRIMARY_RGB,
    TEXT_MUTED_RGB, ACCENT, ACCENT_RGB,
)

class ConversationView(Container):
    """Conversation area that displays messages. It is meant to be placed inside a scrollable container."""
    # Colors come from CSS variables provided by the active Textual theme.
    DEFAULT_CSS = """
    .user-message {
        height: auto;
        background: $panel;
        padding: 1 1;
        margin: 2 0;
        color: $foreground;
    }
    .user-message Static {
        color: $foreground;
    }
    .user-message .command-message {
        color: $accent;
    }
    .assistant-message {
        height: auto;
        margin: 1 0;
        color: $foreground;
        background: $background;
        text-style: bold;
    }
    .system-message {
        margin: 1 0;
        background: $background;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stylize = True
    
    def write(self, text: Union[str, Text]) -> None:
        """Add a message to the conversation.
        
        Accepts either a plain string or a pre-styled Rich Text object.
        """

        # If a pre-styled Text object is passed, mount it directly.
        if isinstance(text, Text):
            self.mount(
                Static(text, classes="system-message")
            )
        elif text.startswith("> "):
            content = text[2:]

            if content.startswith("/"):
                # Command message
                command = Text("> ", style=ACCENT_RGB)
                command.append(content, style=ACCENT_RGB)

                container = Container(
                    Static(command),
                    classes="user-message",
                )
            else:
                # Normal user message
                styled = Text()
                styled.append("> ", style=ACCENT_RGB)
                styled.append(content, style=TEXT_PRIMARY_RGB)

                container = Container(
                    Static(styled),
                    classes="user-message",
                )

            self.mount(container)

        elif text.startswith("✦"):
            # Assistant message with Markdown rendering
            content = text[1:].strip()
            markdown = Markdown(content, code_theme="monokai")

            container = Container(
                Static(markdown),
                classes="assistant-message",
            )

            self.mount(container)

        else:
            # Plain system message (strip any legacy Rich markup tags)
            clean = Text.from_markup(text)
            self.mount(
                Static(clean, classes="system-message")
            )

        # Scroll to bottom
        if self.parent and hasattr(self.parent, "scroll_end"):
            self.refresh(layout=True)
            self.parent.refresh(layout=True)
            self.parent.scroll_end(animate=False)

    def clear(self) -> None:
        """Clear all messages."""
        self.remove_children()
