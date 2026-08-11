import asyncio
import os
import sys
from rich.status import Status
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
from app.theme import (
    BG_MAIN, BG_INPUT, TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER_LIGHT, BORDER_MEDIUM, ACCENT_RGB,
)

class MainApp(App):
    CSS = f"""
    App {{
        background: {BG_MAIN};
    }}
    #main_container {{
        layout: grid;
        grid-size: 1;
        grid-rows: 1fr 1 auto 1;
        height: 100%;
        background: {BG_MAIN};
    }}
    #scrollable_area {{
        height: 1fr;
        border: solid {BORDER_LIGHT};
        background: {BG_MAIN};
        overflow-y: auto;
    }}
    #status {{
        height: 1;
        background: {BG_MAIN};
        color: {TEXT_SECONDARY};
    }}
    #input_area {{
        layout: vertical;
        height: auto;
        min-height: 3;
        border: solid {BORDER_LIGHT};
        padding: 0;
        background: {BG_MAIN};
    }}
    #suggestions {{
        background: {BG_MAIN};
    }}
    #permission_selector {{
        display: none;
        height: 6;
        background: {BG_MAIN};
        border: solid {BORDER_MEDIUM};
    }}
    #permission_selector.visible {{
        display: block;
    }}
    #input_box {{
        height: 3;
        padding: 0 1;
        color: {TEXT_PRIMARY};
        background: {BG_INPUT};
    }}
    #input_box .input {{
        color: {TEXT_PRIMARY};
        background: {BG_INPUT};
    }}
    #input_box .placeholder {{
        color: {TEXT_SECONDARY};
    }}
    #logo {{ align-horizontal: center; margin-bottom: 1; }}
    #conversation {{
        height: auto;
        overflow-y: hidden;
    }}
    #footer {{
        height: 1;
        background: {BG_MAIN};
        color: {TEXT_SECONDARY};
    }}
    """

    def __init__(self):
        super().__init__()
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

    def on_mount(self) -> None:
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
            'on_status': self._on_agent_status,
            # 'on_question': self._on_agent_question,
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

        # Permission requests are now handled via the selector, not via text input.
        # Remove the old text-based permission handling.
        # Keep only agent question handling.

        # If we are waiting for a response to an agent question, handle it specially
        # if self.waiting_for_agent_response and self.agent and self.agent.running:
        #     # Display the user's response in the conversation
        #     conversation.write(f"> (response) {text}")
        #     # Set status to Thinking and disable input while agent processes
        #     status_bar = self.query_one("#status")
        #     status_bar.start_elapsed_timer("Thinking...")
        #     input_box = self.query_one("#input_box")
        #     input_box.disabled = True
        #     # Provide the response to the agent
        #     self.waiting_for_agent_response = False
        #     self.agent.provide_response(text)
        #     # Do not process as a new prompt
        #     return
        # elif self.waiting_for_agent_response:
        #     # Agent is not running but waiting flag is set - reset it
        #     self.waiting_for_agent_response = False
        #     self.set_status_with_input("Ready")
        #     # Fall through to treat as normal prompt

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

        if text.startswith("/"):
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

    def set_status_with_input(self, status_text: str) -> None:
        """Set status bar text and enable/disable input box accordingly."""
        status = self.query_one("#status")
        input_box = self.query_one("#input_box")
        
        status.set_status(status_text)
        # Update terminal window title
        sys.__stdout__.buffer.write(f"\x1b]0;DeepSeekCli - {status_text}\x07".encode())
        sys.__stdout__.buffer.flush()
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
        # Run agent in background thread
        self.agent.run(prompt)

    def handle_command(self, command: str, conversation, status) -> None:
        parts = command[1:].strip().lower().split()
        if not parts:
            return
        cmd = parts[0]

        if cmd == "clear":
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
        else:
            conversation.write(f"Unknown command: {command}")
            self.set_status_with_input("Ready")

        self.query_one("#input_box").focus()

    # Callback methods for agent
    def _on_agent_message(self, message: str) -> None:
        """Called when agent sends a message."""
        conversation = self.query_one("#conversation")
        conversation.write(f"\u2726 {message}")
        self.call_after_refresh(self._scroll_to_bottom)

    def _on_agent_tool(self, tool_data: dict) -> None:
        """Called when agent executes a tool. Displays tool name with relevant arguments."""
        tool = tool_data.get('tool', 'unknown')
        args = tool_data.get('arguments', {})
        conversation = self.query_one("#conversation")

        # Display names for all tools
        display_names = {
            "read_file": "ReadFile",
            "list_directory": "ListDir",
            "write_file": "WriteFile",
            "run_command": "RunCommand",
            "replace": "Replace",
            "glob": "Glob",
            "grep_search": "GrepSearch",
            "run_shell_command": "RunCommand",
            "list_background_processes": "ListBgProcesses",
            "read_background_output": "ReadBgOutput",
            "kill_process": "KillProcess",
            "enter_plan_mode": "PlanMode",
            "google_web_search": "WebSearch",
            "web_fetch": "WebFetch",
            "current_path": "CurrentPath",
            "search_file": "SearchFile",
        }
        display = display_names.get(tool, tool)

        # Build descriptive message based on tool type
        if tool in ("run_command", "run_shell_command"):
            cmd = args.get('command', '')
            bg = args.get('background', False)
            if bg:
                msg = f"[bg] {cmd}"
            else:
                msg = cmd
        elif tool in ("read_file", "write_file", "replace"):
            path = args.get('path', '') or args.get('filePath', '')
            msg = path
        elif tool == "list_directory":
            path = args.get('path', '.')
            msg = path
        elif tool == "current_path":
            msg = ""
        elif tool == "search_file":
            pattern = args.get('pattern', '')
            path = args.get('path', '')
            msg = f"{pattern} in {path}" if path else pattern
        elif tool == "grep_search":
            pattern = args.get('pattern', '')
            path = args.get('path', '')
            include = args.get('include', '')
            parts = [f'"{pattern}"']
            if path:
                parts.append(f"in {path}")
            if include:
                parts.append(f"[{include}]")
            msg = " ".join(parts)
        elif tool == "glob":
            pattern = args.get('pattern', '*')
            path = args.get('path', '')
            msg = f"{pattern}" + (f" in {path}" if path else "")
        elif tool == "read_background_output":
            proc_id = args.get('id', '')
            msg = proc_id
        elif tool == "kill_process":
            proc_id = args.get('id', '')
            msg = proc_id
        elif tool == "enter_plan_mode":
            plan = args.get('plan', True)
            msg = "ON" if plan else "OFF"
        elif tool == "google_web_search":
            query = args.get('query', '')
            msg = f'"{query}"'
        elif tool == "web_fetch":
            url = args.get('url', '')
            msg = url
        elif tool == "list_background_processes":
            msg = ""
        else:
            msg = ""

        # Build the styled output
        check = Text("\u2713 ", style=ACCENT_RGB)
        display_text = Text(display, style="bold")
        if msg:
            msg_text = Text(f" \u00b7 {msg}", style="dim")
            tool_msg = Text.assemble(check, display_text, msg_text)
        else:
            tool_msg = Text.assemble(check, display_text)
        conversation.write(tool_msg)
        self.call_after_refresh(self._scroll_to_bottom)

    def _on_agent_status(self, status: str) -> None:
        """Called when agent status changes."""
        status_bar = self.query_one("#status")
        if status == 'running':
            if not self.timer_active:
                status_bar.start_elapsed_timer("Thinking...")
                self.timer_active = True
            sys.__stdout__.buffer.write(b"\x1b]0;DeepSeekCli - Thinking...\x07")
            sys.__stdout__.buffer.flush()
        elif status == 'waiting':
            status_bar.set_status("Ready")
            self.timer_active = False
            sys.__stdout__.buffer.write(b"\x1b]0;DeepSeekCli - Ready\x07")
            sys.__stdout__.buffer.flush()
            input_box = self.query_one("#input_box")
            input_box.disabled = False
            input_box.focus()
        elif status == 'finished':
            status_bar.set_status("Ready")
            self.timer_active = False
            self.set_status_with_input("Ready")
        else:
            status_bar.set_status(status)
            sys.__stdout__.buffer.write(f"\x1b]0;DeepSeekCli - {status}\x07".encode())
            sys.__stdout__.buffer.flush()

    def _on_agent_question(self, question: str) -> None:
        """Called when agent asks a question."""
        conversation = self.query_one("#conversation")
        conversation.write(f"[white]Agent asks: {question}[/white]")
        self.waiting_for_agent_response = True
        input_box = self.query_one("#input_box")
        input_box.disabled = False
        input_box.focus()
        self.call_after_refresh(self._scroll_to_bottom)

    def _on_agent_finish(self, message: str) -> None:
        """Called when agent finishes."""
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
        tool = data.get('tool', 'unknown')
        args = data.get('args', {})
        conversation = self.query_one("#conversation")
        conversation.write(f"[yellow]Permission required: Tool '{tool}' with arguments: {args}[/yellow]")
        conversation.write("Use arrow keys to select an option and press Enter.")
        self.waiting_for_permission_response = True
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

    def _scroll_to_bottom(self) -> None:
        """Scroll the scrollable area to the bottom."""
        scrollable = self.query_one("#scrollable_area")
        scrollable.scroll_end(animate=False)
