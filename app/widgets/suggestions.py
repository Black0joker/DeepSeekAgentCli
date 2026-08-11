from textual.widgets import ListView, ListItem, Static
from textual.containers import Horizontal
from textual.message import Message

from app.command_defs import Command
from app.theme import ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, BORDER_MEDIUM, BG_MAIN

class CommandListItem(ListItem):
    """Custom ListItem for displaying a command with name and description."""
    def __init__(self, command: Command, name_width: int = 15):
        self.command = command
        name_text = command.name.ljust(name_width)
        desc_text = command.description
        name_static = Static(name_text, classes="command-name")
        desc_static = Static(desc_text, classes="command-desc")
        container = Horizontal(name_static, desc_static, classes="command-row")
        super().__init__(container)

class SuggestionsList(ListView):
    DEFAULT_CSS = f"""
    SuggestionsList {{
        display: none;
        overflow-y: auto;
        background: {BG_MAIN};
        border: solid {BORDER_MEDIUM};
    }}
    SuggestionsList.visible {{
        display: block;
    }}
    SuggestionsList ListItem {{
        height: 1;
        padding: 0;
    }}
    SuggestionsList ListItem > Widget {{
        height: 1;
    }}
    .command-row {{
        height: 1;
        padding: 0 1;
    }}
    .command-name {{
        color: {ACCENT};
        width: 15;
    }}
    .command-desc {{
        color: {TEXT_SECONDARY};
    }}
    .highlight .command-name {{
        color: {TEXT_PRIMARY};
    }}
    .highlight .command-desc {{
        color: {TEXT_PRIMARY};
    }}
    .highlight {{
        background: $accent;
    }}
    """

    class Selected(Message):
        def __init__(self, value: str):
            self.value = value
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._items = []
        self._highlighted_index = 0
        self.display = False
        self._min_visible = 4
        self._max_visible = 8

    def show(self) -> None:
        self.display = True
        self.add_class("visible")
        self._sync_height()
        self.refresh()

    def hide(self) -> None:
        self.display = False
        self.remove_class("visible")
        self.styles.height = "0"
        self.refresh()

    def _sync_height(self) -> None:
        """Set widget height between _min_visible and _max_visible based on item count."""
        count = len(self._items) if self._items else 0
        if count == 0:
            self.styles.height = "0"
            return
        # Always show at least _min_visible rows, at most _max_visible
        visible = max(self._min_visible, min(count, self._max_visible))
        self.styles.height = f"{visible}"

    def update_items(self, items: list[Command]) -> None:
        """Update the list of suggestions with Command objects."""
        self.clear()
        self._items = items
        if not items:
            self.hide()
            return
        max_name_len = max(len(cmd.name) for cmd in items) if items else 15
        for cmd in items:
            self.append(CommandListItem(cmd, max_name_len))
        self._highlighted_index = 0
        self._highlight_item(0)
        self.show()

    def _highlight_item(self, index: int) -> None:
        """Highlight the item at the given index (0-based)."""
        if not self._items or index < 0 or index >= len(self._items):
            return
        for child in self.children:
            child.remove_class("highlight")
        child = self.children[index]
        child.add_class("highlight")
        self._highlighted_index = index
        self.scroll_to_widget(child, animate=False)

    def move_up(self) -> None:
        """Move highlight up."""
        if not self.display or not self._items:
            return
        new_index = (self._highlighted_index - 1) % len(self._items)
        self._highlight_item(new_index)

    def move_down(self) -> None:
        """Move highlight down."""
        if not self.display or not self._items:
            return
        new_index = (self._highlighted_index + 1) % len(self._items)
        self._highlight_item(new_index)

    def get_selected_value(self) -> str | None:
        """Return the name of the currently highlighted command, or None."""
        if not self._items:
            return None
        return self._items[self._highlighted_index].name

    def select_current(self) -> None:
        """Select the currently highlighted item and emit Selected event."""
        value = self.get_selected_value()
        if value is not None:
            self.post_message(self.Selected(value))

    def close(self) -> None:
        """Hide the suggestions list."""
        self.hide()
