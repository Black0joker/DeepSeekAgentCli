from textual.widgets import Static
from textual.containers import Container
from rich.text import Text
from rich.markdown import Markdown
from typing import Union
from app.theme import (
    BG_MAIN, BG_INPUT, TEXT_PRIMARY, TEXT_PRIMARY_RGB,
    TEXT_MUTED_RGB, ACCENT, ACCENT_RGB,
)

class ConversationView(Container):
    """Conversation area that displays messages. It is meant to be placed inside a scrollable container."""
    DEFAULT_CSS = f"""
    .user-message {{
        height:3;
        background: {BG_INPUT};
        padding: 1 1;
        margin: 2 0;
        color: {TEXT_PRIMARY};
    }}
    .user-message Static {{
        color: {TEXT_PRIMARY};
    }}
    .user-message .command-message {{
        color: {ACCENT};
    }}
    .assistant-message {{
        margin: 1 0;
        color: {TEXT_PRIMARY};
        background: {BG_MAIN};
        text-style: bold;
    }}
    .system-message {{
        margin: 1 0;
        background: {BG_MAIN};
    }}
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

        elif text.startswith("\u2726"):
            # Assistant message with Markdown rendering
            content = text[1:].strip()
            markdown = Markdown(content, code_theme="monokai")

            container = Container(
                markdown,
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
