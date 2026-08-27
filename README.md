# DeepSeekCli

A **terminal-based UI (TUI) client** for the DeepSeek chat API, built with the [Textual](https://textual.textualize.io/) framework. Functions as an **Autonomous Software Engineering Agent** that can iteratively plan, execute tools, and verify results through natural language conversation.

![Python](https://img.shields.io/badge/Python-3.13+-blue) ![Textual](https://img.shields.io/badge/Textual-TUI-purple) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with your DeepSeek credentials
echo DS_SMIDV2=your_value >> app/agent/.env
echo DS_SESSION_ID=your_value >> app/agent/.env
echo DS_AUTHORIZATION=your_value >> app/agent/.env

# Run
python main.py
```

## Features

### Agent

- **Autonomous Planning** — Observes, plans, acts, verifies, and adapts
- **Rich Tool Execution** — 17 tools for file operations, search, shell commands, background processes, and web access
- **Advanced Code Editing** — 7-layer safety-first matching engine with confidence scoring, fuzzy candidate discovery, and atomic writes
- **Background Process Management** — Run long-running commands asynchronously, track, read output, and kill them
- **Permission Mode** — `auto` (all tools allowed) or `permission` (approve each write/exec tool)
- **Session Management** — Create, list, and switch between DeepSeek chat sessions
- **Workspace Context** — Configurable workspace directory for all file operations

### Agent Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with optional offset/limit |
| `write_file` | Create or completely replace a file |
| `replace` | Safe surgical code editing with 7-layer matching engine |
| `list_directory` | List directory contents |
| `current_path` | Returns workspace path |
| `search_file` | Search for files by name pattern |
| `glob` | Find files matching glob patterns (e.g., `**/*.py`) |
| `grep_search` | Regex/text search inside files with optional include filter |
| `run_shell_command` | Execute commands with background support and timeout |
| `code_interpreter` | Execute Python code via `python -c` |
| `list_background_processes` | List all tracked background tasks |
| `read_background_output` | Read output from a background process |
| `kill_process` | Terminate a background process by ID |
| `enter_plan_mode` | Toggle read-only plan mode (write/execute tools are blocked while active) |
| `google_web_search` | Search the web for information |
| `web_fetch` | Fetch content from web pages |
| `ask_user` | Ask the user a question and wait for the answer |
| `user_response` | Deliver the final response and finish the run |

### UI

- **Conversation View** — Agent messages, tool executions with rich context display (paths, commands, patterns)
- **Tool Display** — Each tool execution shows: `✓ ToolName · argument` (e.g., `✓ ReadFile · src/main.py`, `✓ RunCommand · pytest`)
- **Command Suggestions** — Type `/` to see all commands, arrow keys to navigate, Enter/Tab to select
- **Status Bar** — Elapsed timer with animated spinner during agent processing
- **Permission Selector** — Interactive allow once / allow for session / reject UI
- **Streaming Responses** — `user_response`/`ask_user` text is detected directly in the SSE stream and rendered live, chunk by chunk, until the JSON ends
- **Multi-threaded** — Agent runs in background threads, keeping the UI responsive

## Commands

| Command | Description |
|---------|-------------|
| `/clear` | Clear the conversation |
| `/help` | Show available commands |
| `/new` | Start a new conversation |
| `/settings` | Display current settings |
| `/theme [name]` | Show or switch the UI theme (presets: default, dracula, gruvbox, nord, monokai, solarized_dark) |
| `/mode [auto|permission]` | Show or set operation mode |
| `/set_workspace <path>` | Set the workspace directory |
| `/change_chat <number>` | Switch to a chat session by number |
| `/chats` | List all chat sessions (follows pagination) |
| `/export` | Export the current conversation to a Markdown file |
| `/quit` | Exit the application |

## Architecture

```
DeepSeekCli/
├── main.py                  # Entry point
├── removeChats.py           # Utility to bulk-delete chat sessions
├── test_sse_parser.py       # SSE parser test / smoke harness
├── requirements.txt         # Python dependencies
├── system.md                # System prompt for the autonomous agent
├── app/
│   ├── app.py               # Main Textual App (UI layout, CSS, event handling)
│   ├── agent_wrapper.py     # Bridges agent logic with Textual UI (background threads)
│   ├── command_defs.py      # Canonical command definitions
│   ├── commands/            # Backward-compatible re-exports of command_defs
│   ├── theme/
│   │   └── __init__.py      # Centralized palette + Textual theme builder
│   ├── state/
│   │   └── app_state.py     # Application state (model, workspace, mode)
│   ├── agent/
│   │   ├── module.py        # DeepSeekClient API, tool execution, background processes
│   │   ├── sse_parser.py    # SSE stream parser for DeepSeek responses
│   │   ├── edit_file.py     # 7-layer safety-first code editing engine
│   │   ├── config.py        # Environment configuration (.env loading)
│   │   ├── logger.py        # Rotating file + console logging utility
│   │   └── algorithmFunction.py  # PoW (Proof of Work) WASM solver
│   └── widgets/
│       ├── conversation.py  # Chat message display (Rich Text support)
│       ├── input_box.py     # User input field with key handling
│       ├── suggestions.py   # Command suggestion dropdown
│       ├── permission.py    # Tool permission selector
│       ├── tool_entry.py    # Live tool-call entry with animated spinner
│       ├── tool_writer.py   # Tool call/result formatting
│       ├── footer.py        # Bottom status bar (workspace, branch, mode, thinking)
│       ├── header.py        # Top header bar
│       ├── status.py        # Elapsed time / spinner / status indicator
│       └── logo.py          # Gradient ASCII logo
├── config/                  # Configuration directory (theme.json)
├── assets/                  # Assets directory (reserved)
└── logs/                    # Agent log files
```

## Code Editing Engine

The `replace` tool uses a sophisticated 7-layer matching engine (`app/agent/edit_file.py`):

| Layer | Strategy | Confidence | Auto-Edit? |
|-------|----------|-----------|------------|
| 1 | Exact match | 1.0 | ✓ |
| 2 | Line-ending normalized | 0.98 | ✓ |
| 3 | Indentation-normalized | 0.95 | ✓ |
| 4 | Whitespace-normalized | 0.92 | ✓ |
| 5 | Operator-spacing normalized | 0.90 | ✓ |
| 6 | Structural/language-aware | 0.88 | Extension point |
| 7 | Fuzzy candidate discovery | varies | ✗ (never) |

**Safety guarantees:**
- Multiple matches → `ambiguous_match` error (never edits blindly)
- Fuzzy matches return candidates for inspection only
- Atomic writes via temp-file + rename (crash-safe)
- Preserves original file line endings
- Dry-run mode for previewing edits
- Structured results with match_type, confidence, line numbers, and diff preview

## Theme

All colors are centralized in `app/theme/__init__.py`:

- **Accent**: `#C792EA` (purple) — commands, highlights
- **Background**: `#000000` (black) — main UI
- **Input**: `#292929` (dark gray) — input box
- **Text**: `#FFFFFF` (white), `#A0A0A0` (gray), `#DCDCDC` (muted)
- **Borders**: Subtle `rgba(255,255,255,0.08)` and visible `rgba(255,255,255,0.2)`

## How It Works

1. Loads API credentials from `.env`, creates a DeepSeek chat session
2. Sends system prompt defining agent behavior and JSON protocol
3. User types a natural language request
4. Agent loop: send prompt → parse SSE response → execute tools → feed results back → repeat
5. Tools operate within the configured workspace directory
6. Tool executions are displayed in the conversation with rich context (paths, commands, patterns)

## Build

```bash
pyinstaller --onefile --name DeepSeekCli main.py
```

Outputs `DeepSeekCli.exe` in `dist/`. (`.spec` files are gitignored — keep a
local copy if you maintain a custom spec.)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13+ |
| TUI Framework | Textual |
| HTTP Client | Requests |
| Rich Text | Rich |
| API | DeepSeek Chat API (SSE) |
| Build | PyInstaller |
| WASM Runtime | wasmtime (PoW solving) |
| Background Processes | threading + subprocess |

## License

MIT
