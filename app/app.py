import os
import sys
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from .widgets.header import CustomHeader
from .widgets.conversation import ConversationView
from .widgets.input_box import InputBox
from .widgets.footer import CustomFooter
from .widgets.status import StatusBar
from .widgets.suggestions import SuggestionsList
from .widgets.permission import PermissionSelector
from .widgets import Logo
from .state import AppState
from app.command_defs import COMMANDS
from .agent_wrapper import AgentWrapper
from .widgets.tool_writer import format_tool_done
from .widgets.tool_entry import ToolCallEntry
from app.theme import (
    ACCENT_RGB,
    load_theme, list_presets, get_theme, build_textual_theme,
)

class MainApp(App):
    BINDINGS = [
        ("ctrl+t", "toggle_thinking", "Toggle thinking mode"),
    ]

    # All colors are resolved from CSS variables provided by the active
    # Textual theme (see app.theme.build_textual_theme), so switching the
    # theme at runtime restyles the whole UI.
    CSS = """
    App {
        background: $background;
    }
    #main_container {
        layout: grid;
        grid-size: 1;
        grid-rows: 1fr 1 auto 1;
        height: 100%;
        background: $background;
    }
    #scrollable_area {
        height: 1fr;
        border: solid $border-light;
        background: $background;
        overflow-y: auto;
    }
    #status {
        height: 1;
        background: $background;
        color: $text-secondary;
    }
    #input_area {
        layout: vertical;
        height: auto;
        min-height: 3;
        border: solid $border-light;
        padding: 0;
        background: $background;
    }
    #suggestions {
        background: $background;
    }
    #permission_selector {
        display: none;
        height: 6;
        background: $background;
        border: solid $border-medium;
    }
    #permission_selector.visible {
        display: block;
    }
    #input_box {
        height: 3;
        padding: 0 1;
        color: $foreground;
        background: $panel;
    }
    #input_box .input {
        color: $foreground;
        background: $panel;
    }
    #input_box .placeholder {
        color: $text-secondary;
    }
    #logo { align-horizontal: center; margin-bottom: 1; }
    #conversation {
        height: auto;
        overflow-y: hidden;
    }
    #footer {
        height: 1;
        background: $background;
        color: $text-secondary;
    }
    """

    def __init__(self):
        super().__init__()
        # Load the palette config and register the derived Textual theme
        # BEFORE the startup stylesheet parse, so custom CSS variables
        # ($border-light, $text-secondary, ...) are defined at parse time.
        load_theme()
        self._apply_textual_theme()
        self.state = AppState()
        self.suggestions = SuggestionsList(id="suggestions")
        self.suggestions.hide()
        self.permission_selector = PermissionSelector(id="permission_selector")
        self.permission_selector.display = False
        self.agent = None
        self.chat_sessions = []
        self.waiting_for_agent_response = False
        self.waiting_for_permission_response = False
        self.timer_active = False
        # Maps agent call_id -> ToolCallEntry widget currently running
        self._tool_entries = {}
        # Buffer for streaming thinking text into the status bar line by line
        self._thinking_buffer = ""
        # Live streaming of user_response/ask_user text while the JSON arrives
        self._response_stream_entry = None
        self._response_stream_buffer = ""
        

    def compose(self) -> ComposeResult:
        with Container(id="main_container"):
            with VerticalScroll(id="scrollable_area"):
                yield Logo(id="logo")
                yield CustomHeader(id="header")
                yield ConversationView(id="conversation")
            yield StatusBar(id="status")
            with Container(id="input_area"):
                yield self.suggestions
                yield self.permission_selector
                yield InputBox(id="input_box")
            yield CustomFooter(id="footer")

    def action_toggle_thinking(self) -> None:
        """Toggle thinking mode and update the footer."""
        new_mode = self.state.toggle_thinking_mode()
        conversation = self.query_one("#conversation")
        conversation.write(f"Thinking mode toggled to: {new_mode}")
        self.query_one("#footer").refresh()

    def _apply_textual_theme(self) -> None:
        """Register and activate the Textual theme built from the palette.

        Setting ``App.theme`` reparses the stylesheet with the new CSS
        variables and restyles every widget live. The stylesheet variables
        are also synced immediately so that a startup CSS parse (which runs
        before reactive watchers fire) already sees the custom variables.
        """
        theme = build_textual_theme()
        self.register_theme(theme)
        self.theme = theme.name
        try:
            self.stylesheet.set_variables(self.get_css_variables())
        except Exception:
            # Stylesheet may not exist in edge cases; the reactive watcher
            # will sync variables on the next theme change.
            pass

    def on_mount(self) -> None:
        # Re-apply the theme in case the config theme differs from the
        # one registered during __init__ (idempotent when unchanged).
        load_theme()
        self._apply_textual_theme()
        # Set workspace to actual current path
        self.state.set_workspace(os.getcwd())
        self.state.set_model("DeepSeek-V3")
        conversation = self.query_one("#conversation")
        conversation.write("Welcome to the terminal UI!")
        conversation.write("Type a message or use /commands (e.g., /clear)")
        conversation.write(f"Available commands: {', '.join([cmd.name for cmd in COMMANDS])}")
        self.suggestions.hide()
        
        # Initialize the agent
        self.agent = AgentWrapper(self)
        callbacks = {
            'on_message': self._on_agent_message,
            'on_tool': self._on_agent_tool,
            'on_tool_result': self._on_agent_tool_result,
            'on_thinking': self._on_agent_thinking,
            'on_thinking_done': self._on_agent_thinking_done,
            'on_response_delta': self._on_agent_response_delta,
            'on_status': self._on_agent_status,
            'on_question': self._on_agent_question,
            'on_finish': self._on_agent_finish,
            'on_error': self._on_agent_error,
            'on_permission_request': self._on_permission_request,
        }
        self.agent.register_callbacks(callbacks)
        
        # Set status to Initializing and disable input before starting the thread
        self.set_status_with_input("Initializing...")
        
        # Initialize agent in a background thread to avoid blocking the UI
        self.agent.initialize_in_thread(self._on_agent_initialized)
        
        self.query_one("#input_box").focus()
    
    def _on_agent_initialized(self, success: bool) -> None:
        """Callback for when agent initialization completes in the background thread."""
        conversation = self.query_one("#conversation")
        if success:
            conversation.write("Agent initialized successfully.")
        else:
            conversation.write("Agent initialization failed. Check logs.")
        # Reset status to Ready
        self.set_status_with_input("Ready")

    def on_input_box_text_changed(self, event: InputBox.TextChanged) -> None:
        text = event.text
        if text.startswith("/"):
            matches = [cmd for cmd in COMMANDS if cmd.name.startswith(text)]
            if matches:
                self.suggestions.update_items(matches)
            else:
                self.suggestions.hide()
                self.suggestions.refresh()
        else:
            self.suggestions.hide()
            self.suggestions.refresh()

    def on_input_box_message_sent(self, event: InputBox.MessageSent) -> None:
        text = event.text
        if not text.strip():
            return
        conversation = self.query_one("#conversation")
        status = self.query_one("#status")

        # If this is a command that requires arguments but none provided, keep input open
        if text.startswith("/"):
            parts = text.split()
            if len(parts) == 1:
                cmd_name = parts[0]
                if self.command_requires_args(cmd_name):
                    input_box = self.query_one("#input_box")
                    input_box.text = text + " "
                    input_box.cursor_position = len(input_box.text)
                    input_box.focus()
                    return

        # Normal prompt handling
        conversation.write(f"> {text}")
        self.suggestions.hide()
        self.suggestions.refresh()

        if self.waiting_for_agent_response:
            # Agent is waiting for user's answer to a question
            self.waiting_for_agent_response = False
            self.agent.provide_response(text)
            self.set_status_with_input("Thinking...")
        elif text.startswith("/"):
            self.handle_command(text, conversation, status)
        else:
            # Start the agent with the user's prompt
            self.start_agent(text)

    def on_input_box_suggestion_selected(self, event: InputBox.SuggestionSelected) -> None:
        input_box = self.query_one("#input_box")
        input_box.apply_suggestion(event.text)
        self.suggestions.hide()
        self.suggestions.refresh()
        input_box.focus()

    def on_suggestions_list_selected(self, event: SuggestionsList.Selected) -> None:
        value = event.value
        input_box = self.query_one("#input_box")
        input_box.apply_suggestion(value)
        self.suggestions.hide()
        self.suggestions.refresh()
        input_box.focus()

    def command_requires_args(self, cmd_name: str) -> bool:
        """Check if a command requires additional arguments."""
        for cmd in COMMANDS:
            if cmd.name == cmd_name:
                return cmd.requires_arguments
        return False

    def _set_terminal_title(self, status_text: str) -> None:
        """Update the terminal window title (best effort, never raises)."""
        try:
            stdout = sys.__stdout__
            if stdout is None or not hasattr(stdout, "buffer"):
                return
            stdout.buffer.write(f"\x1b]0;DeepSeekCli - {status_text}\x07".encode())
            stdout.buffer.flush()
        except Exception:
            pass

    def set_status_with_input(self, status_text: str) -> None:
        """Set status bar text and enable/disable input box accordingly."""
        status = self.query_one("#status")
        input_box = self.query_one("#input_box")

        status.set_status(status_text)
        # Update terminal window title
        self._set_terminal_title(status_text)
        # Disable input when not Ready, enable when Ready
        input_box.disabled = (status_text != "Ready")
        if status_text=="Ready":
            input_box.focus()

    def start_agent(self, prompt: str) -> None:
        """Start the agent with the given prompt."""
        if self.agent is None:
            conversation = self.query_one("#conversation")
            conversation.write("Agent not initialized.")
            return
        if self.agent.running:
            conversation = self.query_one("#conversation")
            conversation.write("Agent is already running.")
            return
        # Disable input and set status
        self.set_status_with_input("Thinking...")
        # Reset thinking stream buffer for the new run
        self._thinking_buffer = ""
        # Run agent in background thread
        self.agent.run(prompt)

    def handle_command(self, command: str, conversation, status) -> None:
        parts = command[1:].strip().lower().split()
        if not parts:
            return
        cmd = parts[0]

        if cmd == "clear":
            self._finalize_response_stream()
            conversation.clear()
            self.set_status_with_input("Ready")
        elif cmd == "help":
            conversation.write(f"Available commands: {', '.join([c.name for c in COMMANDS])}")
            self.set_status_with_input("Ready")
        elif cmd == "new":
            conversation.clear()
            conversation.write("New conversation started.")
            self.set_status_with_input("Ready")
        elif cmd == "settings":
            settings_str = ", ".join(f"{k}={v}" for k, v in self.state.settings.items()) if self.state.settings else "No settings configured."
            conversation.write(f"Settings: {settings_str}")
            self.set_status_with_input("Ready")
        elif cmd == "mode":
            if len(parts) == 1:
                # Toggle mode without argument
                new_mode = "permission" if self.state.mode == "auto" else "auto"
                self.state.set_mode(new_mode)
                conversation.write(f"Mode toggled to: {new_mode}")
                self.query_one("#footer").refresh()
            else:
                new_mode = parts[1].lower()
                if new_mode in ("auto", "permission"):
                    self.state.set_mode(new_mode)
                    conversation.write(f"Mode changed to: {new_mode}")
                    self.query_one("#footer").refresh()
                else:
                    conversation.write(f"Invalid mode: {new_mode}. Valid modes: auto, permission")
            self.set_status_with_input("Ready")
        elif cmd == "theme":
            if len(parts) == 1:
                # Show current theme and available presets
                current = get_theme()
                presets = list_presets()
                conversation.write(f"Current theme: [bold]{current['name']}[/bold]")
                conversation.write(f"Available presets: {', '.join(presets)}")
                conversation.write("Use /theme <name> to switch. Create config/theme.json for custom themes.")
            else:
                theme_name = parts[1].lower()
                if load_theme(theme_name):
                    self._apply_textual_theme()
                    conversation.write(f"Theme changed to: [bold]{theme_name}[/bold]")
                    # Refresh Rich-rendered widgets that read palette globals
                    self.query_one("#logo").refresh()
                    self.query_one("#footer").refresh()
                    self.refresh()
                else:
                    conversation.write(f"Theme '{theme_name}' not found. Available: {', '.join(list_presets())}")
            self.set_status_with_input("Ready")
        elif cmd == "quit":
            self.exit()
        elif cmd == "set_workspace":
            if len(parts) == 1:
                conversation.write(f"Current workspace: {self.state.workspace}. Use /set_workspace <path> to change.")
            else:
                # Preserve original casing from the raw command (parts are lowercased)
                raw_after_cmd = command[len("/set_workspace "):].strip()
                new_path = os.path.abspath(raw_after_cmd)
                # Validate the path exists
                if os.path.isdir(new_path):
                    self.state.set_workspace(new_path)
                    conversation.write(f"Workspace changed to: {new_path}")
                    self.query_one("#footer").refresh()
                else:
                    conversation.write(f"Invalid path or directory does not exist: {new_path}")
            self.set_status_with_input("Ready")
        elif cmd == "change_chat":
            if self.agent is None:
                conversation.write("Agent not initialized.")
                self.set_status_with_input("Ready")
            elif len(parts) == 1:
                conversation.write(f"Current chat session: {self.agent.session_id}. Use /chats to list sessions, then /change_chat <number>.")
                self.set_status_with_input("Ready")
            else:
                index_str = parts[1]
                if not index_str.isdigit():
                    conversation.write(f"Invalid chat number: {index_str}. Use /chats to see available numbers.")
                    self.set_status_with_input("Ready")
                else:
                    index = int(index_str)
                    if not self.chat_sessions:
                        conversation.write("No cached chat sessions. Run /chats first.")
                        self.set_status_with_input("Ready")
                    elif index < 1 or index > len(self.chat_sessions):
                        conversation.write(f"Chat number {index} out of range. Available: 1-{len(self.chat_sessions)}. Use /chats to see the list.")
                        self.set_status_with_input("Ready")
                    else:
                        chat = self.chat_sessions[index - 1]
                        chat_id = chat.get("id")
                        title = chat.get("title", "Untitled")
                        if not chat_id:
                            conversation.write("Selected chat has no valid ID.")
                            self.set_status_with_input("Ready")
                        else:
                            conversation.write(f"Switching to [bold]{title}[/bold]...")
                            self.set_status_with_input("Changing Chat...")
                            self.agent.change_chat_in_thread(chat_id, self._on_change_chat_complete)
        elif cmd == "chats":
            if self.agent is None:
                conversation.write("Agent not initialized.")
                self.set_status_with_input("Ready")
            else:
                self.set_status_with_input("Fetching Chats...")
                self.agent.fetch_chats_in_thread(self._on_fetch_chats_complete)
        elif cmd == "export":
            self._export_conversation(conversation)
            self.set_status_with_input("Ready")
        else:
            conversation.write(f"Unknown command: {command}")
            self.set_status_with_input("Ready")

        self.query_one("#input_box").focus()

    # Callback methods for agent

    def _finalize_response_stream(self) -> None:
        """Remove the live streaming entry (if any) before the final message
        is written by the normal message handlers."""
        entry = self._response_stream_entry
        self._response_stream_entry = None
        self._response_stream_buffer = ""
        if entry is not None:
            try:
                entry.remove()
            except Exception:
                pass

    def _on_agent_response_delta(self, delta: str) -> None:
        """Stream user_response/ask_user text into the conversation while the
        JSON is still arriving from the SSE stream."""
        if not delta:
            return
        from textual.widgets import Static
        if self._response_stream_entry is None:
            conversation = self.query_one("#conversation")
            entry = Static("", classes="assistant-message streaming-message")
            self._response_stream_entry = entry
            conversation.mount(entry)
        self._response_stream_buffer += delta
        # Plain Text renderable: streamed text is not interpreted as markup
        self._response_stream_entry.update(Text(self._response_stream_buffer))
        self.call_after_refresh(self._scroll_to_bottom)

    def _on_agent_message(self, message: str) -> None:
        """Called when agent sends a message."""
        self._finalize_response_stream()
        conversation = self.query_one("#conversation")
        conversation.write(f"\u2726 {message}")
        self.call_after_refresh(self._scroll_to_bottom)

    def _on_agent_tool(self, tool_data: dict) -> None:
        """Called when the agent starts executing a tool.

        Mounts a live ToolCallEntry (animated spinner) that will be updated
        in place when the tool result arrives.
        """
        tool = tool_data.get('tool', 'unknown')
        args = tool_data.get('arguments', {})
        call_id = tool_data.get('call_id')
        conversation = self.query_one("#conversation")

        entry = ToolCallEntry(tool, args, call_id=call_id)
        conversation.mount(entry)

        if call_id:
            # Safety cap: discard stale mappings if the result never arrived
            if len(self._tool_entries) > 100:
                self._tool_entries.clear()
            self._tool_entries[call_id] = entry

        self.call_after_refresh(self._scroll_to_bottom)

    def _on_agent_tool_result(self, tool_data: dict) -> None:
        """Called after a tool has finished executing.

        Updates the matching ToolCallEntry in place; falls back to writing
        a static line when no running entry is found.
        """
        tool = tool_data.get('tool', 'unknown')
        args = tool_data.get('arguments', {})
        result = tool_data.get('result', {})
        call_id = tool_data.get('call_id')

        entry = self._tool_entries.pop(call_id, None) if call_id else None
        if entry is not None:
            entry.complete(result)
        else:
            # Fallback: no tracked entry (e.g. session restored mid-run)
            conversation = self.query_one("#conversation")
            main, detail = format_tool_done(tool, args, result)
            if detail is not None:
                main.append("\n")
                main.append_text(detail)
            conversation.write(main)

        self.call_after_refresh(self._scroll_to_bottom)

    # ---- Thinking stream (status bar, line by line) ----

    def _on_agent_thinking(self, chunk: str) -> None:
        """Stream a thinking chunk into the status bar, line by line."""
        if not chunk:
            return
        self._thinking_buffer += chunk
        # Emit every completed line; keep the partial trailing line buffered
        while "\n" in self._thinking_buffer:
            line, self._thinking_buffer = self._thinking_buffer.split("\n", 1)
            self._show_thinking_line(line)

    def _on_agent_thinking_done(self, _data) -> None:
        """Flush any remaining partial thinking line when thinking ends."""
        if self._thinking_buffer:
            remaining = self._thinking_buffer
            self._thinking_buffer = ""
            self._show_thinking_line(remaining)

    def _show_thinking_line(self, line: str) -> None:
        """Display one thinking line in the status bar (truncated to fit)."""
        line = line.strip()
        if not line:
            return
        max_len = 100
        if len(line) > max_len:
            line = line[: max_len - 1] + "\u2026"
        status_bar = self.query_one("#status")
        status_bar.set_status(f"\u2727 {line}")

    def _on_agent_status(self, status: str) -> None:
        """Called when agent status changes."""
        status_bar = self.query_one("#status")
        if status == 'running':
            if not self.timer_active:
                status_bar.start_elapsed_timer("Thinking...")
                self.timer_active = True
            self._set_terminal_title("Thinking...")
        elif status == 'waiting':
            status_bar.set_status("Ready")
            self.timer_active = False
            self._set_terminal_title("Ready")
            input_box = self.query_one("#input_box")
            input_box.disabled = False
            input_box.focus()
        elif status == 'finished':
            status_bar.set_status("Ready")
            self.timer_active = False
            self.set_status_with_input("Ready")
        else:
            status_bar.set_status(status)
            self._set_terminal_title(status)

    def _on_agent_question(self, question: str) -> None:
        """Called when agent asks a question."""
        self._finalize_response_stream()
        conversation = self.query_one("#conversation")
        styled = Text("\u2726 Agent asks: ", style=ACCENT_RGB)
        styled.append(question, style="bold white")
        conversation.write(styled)
        self.waiting_for_agent_response = True
        self.timer_active = False
        status_bar = self.query_one("#status")
        status_bar.set_status("Waiting for your answer...")
        input_box = self.query_one("#input_box")
        input_box.disabled = False
        input_box.focus()
        self.call_after_refresh(self._scroll_to_bottom)

    def _on_agent_finish(self, message: str) -> None:
        """Called when agent finishes."""
        self._finalize_response_stream()
        if message:
            conversation = self.query_one("#conversation")
            styled = Text("Agent finished: ", style=ACCENT_RGB)
            styled.append(message, style=ACCENT_RGB)
            conversation.write(styled)
        # Reset states
        self.waiting_for_agent_response = False
        self.waiting_for_permission_response = False
        self.timer_active = False
        self.set_status_with_input("Ready")
        self.call_after_refresh(self._scroll_to_bottom)
        # Ensure input is enabled and focused
        input_box = self.query_one("#input_box")
        input_box.disabled = False
        input_box.focus()

    def _on_fetch_chats_complete(self, success: bool, data) -> None:
        """Callback for when fetch_chats completes in the background thread."""
        conversation = self.query_one("#conversation")
        if success:
            if isinstance(data, list):
                self.chat_sessions = data
                if data:
                    conversation.write("Chat sessions:")
                    for idx, chat in enumerate(data, start=1):
                        chat_id = chat.get("id", "N/A")
                        title = chat.get("title", "Untitled")
                        conversation.write(f"  [bold]{idx}[/bold]: {title} ([dim]{chat_id}[/dim])")
                else:
                    conversation.write("No chat sessions found.")
            else:
                conversation.write(f"Unexpected response format: {data}")
        else:
            conversation.write(f"[red]Failed to fetch chats: {data}[/red]")
        self.set_status_with_input("Ready")

    def _on_change_chat_complete(self, success: bool, message: str) -> None:
        """Callback for when change_chat completes in the background thread."""
        conversation = self.query_one("#conversation")
        conversation.write(message)
        if success:
            self.query_one("#footer").refresh()
        self.set_status_with_input("Ready")
        self.agent.system_prompt_sent.set()

    def _on_agent_error(self, error: str) -> None:
        """Called when agent encounters an error."""
        conversation = self.query_one("#conversation")
        conversation.write(f"[red]Error: {error}[/red]")
        # Reset states
        self.waiting_for_agent_response = False
        self.waiting_for_permission_response = False
        self.timer_active = False
        self.set_status_with_input("Ready")
        self.call_after_refresh(self._scroll_to_bottom)
        input_box = self.query_one("#input_box")
        input_box.disabled = False
        input_box.focus()

    def _on_permission_request(self, data: dict) -> None:
        """Called when agent requests permission for a tool."""
        import json
        tool = data.get('tool', 'unknown')
        args = data.get('args', {})
        conversation = self.query_one("#conversation")

        # Build detailed permission request message
        args_summary = json.dumps(args, indent=2) if args else "{}"
        conversation.write(
            f"[yellow bold]\U0001F510 Permission Required[/yellow bold]\n"
            f"[yellow]Tool:[/yellow] [bold]{tool}[/bold]\n"
            f"[yellow]Arguments:[/yellow]\n[dim]{args_summary}[/dim]"
        )
        conversation.write(
            "[dim]Press [bold]y[/bold] (allow once), [bold]s[/bold] (allow session), "
            "[bold]n[/bold] (reject), or use arrow keys + Enter[/dim]"
        )
        self.waiting_for_permission_response = True
        # Set tool info on the selector
        self.permission_selector.set_tool_info(tool, args)
        # Show the permission selector and give it focus
        self.permission_selector.display = True
        self.permission_selector.focus()
        # Disable input box to prevent typing
        input_box = self.query_one("#input_box")
        input_box.disabled = True
        self.call_after_refresh(self._scroll_to_bottom)

    def on_permission_selector_selected(self, event: PermissionSelector.Selected) -> None:
        """Handle selection from the permission selector."""
        decision = event.decision
        # Hide the selector
        self.permission_selector.display = False
        self.waiting_for_permission_response = False
        # Enable input box and focus
        input_box = self.query_one("#input_box")
        input_box.disabled = False
        input_box.focus()
        # Send decision to agent
        self.agent.provide_permission_response(decision)
        self.call_after_refresh(self._scroll_to_bottom)

    def _extract_widget_text(self, widget) -> str:
        """Recursively extract text content from a widget (handles Container, Static, etc.)."""
        from textual.widgets import Static
        from textual.containers import Container
        if isinstance(widget, Static):
            try:
                renderable = widget.render()
                return str(renderable) if renderable else ""
            except Exception:
                return ""
        elif hasattr(widget, 'children'):
            # Container or similar - recurse into children
            parts = []
            for child in widget.children:
                parts.append(self._extract_widget_text(child))
            return "\n".join(parts)
        else:
            try:
                renderable = widget.render()
                return str(renderable) if renderable else ""
            except Exception:
                return ""

    def _export_conversation(self, conversation) -> None:
        """Export the current conversation to a Markdown file."""
        import datetime
        children = conversation.children
        lines = [
            "# DeepSeekCli Conversation Export",
            f"Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for child in children:
            text = self._extract_widget_text(child)
            if text.strip():
                lines.append(text)
                lines.append("")

        export_path = os.path.join(
            self.state.workspace,
            f"conversation_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            conversation.write(f"Conversation exported to: [bold]{export_path}[/bold]")
        except OSError as e:
            conversation.write(f"[red]Failed to export: {e}[/red]")

    def _scroll_to_bottom(self) -> None:
        """Scroll the scrollable area to the bottom."""
        scrollable = self.query_one("#scrollable_area")
        scrollable.scroll_end(animate=False)
