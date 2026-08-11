# DeepSeekCli

## Overview

DeepSeekCli is a **terminal-based UI (TUI) client** for the DeepSeek chat API, built with the [Textual](https://textual.textualize.io/) framework. It functions as an **Autonomous Software Engineering Agent** that can iteratively plan, execute tools, and verify results through natural language conversation with the DeepSeek AI model.

## Architecture

```
DeepSeekCli/
├── main.py                  # Entry point
├── removeChats.py           # Utility script to bulk-delete chat sessions
├── project.md               # Project documentation
├── tasks.md                 # Task tracking
├── app/
│   ├── app.py               # Main Textual App (UI layout, event handling, CSS)
│   ├── agent_wrapper.py     # Bridges agent logic with Textual UI (background threads)
│   ├── command_defs.py      # Canonical CLI command definitions (/clear, /help, etc.)
│   ├── commands.py          # Re-exports from command_defs for backward compatibility
│   ├── commands/
│   │   └── __init__.py      # Re-exports from command_defs for backward compatibility
│   ├── theme/
│   │   └── __init__.py      # Centralized color palette (ACCENT, BG_*, TEXT_*, etc.)
│   ├── state/
│   │   ├── __init__.py      # Re-exports AppState
│   │   └── app_state.py     # Application state (model, workspace, mode, permissions)
│   ├── agent/
│   │   ├── module.py        # DeepSeekClient API, SSE parser, tool execution
│   │   ├── config.py        # Environment variable & .env configuration
│   │   ├── logger.py        # Colored logging utility
│   │   ├── algorithmFunction.py  # PoW (Proof of Work) WASM solver
│   │   ├── system.md        # System prompt for the autonomous agent
│   │   └── requirements.txt # Python dependencies
│   └── widgets/
│       ├── __init__.py      # Widget re-exports
│       ├── conversation.py  # Chat message display (Rich Text support)
│       ├── input_box.py     # User input field with key handling
│       ├── header.py        # Top header bar
│       ├── footer.py        # Bottom status bar (workspace, branch, model, mode)
│       ├── status.py        # Elapsed time / spinner / status indicator
│       ├── suggestions.py   # Command suggestion dropdown (ListView-based)
│       ├── permission.py    # Tool permission selector (allow once/session/reject)
│       └── logo.py          # Gradient ASCII logo display
├── config/                  # Configuration directory (reserved)
├── assets/                  # Assets directory (reserved)
└── logs/                    # Agent log files
```

## Features

### Agent Capabilities
- **Autonomous Planning**: The agent uses a system prompt that instructs it to observe, plan, act, verify, and adapt
- **Tool Execution**: Supports `read_file`, `write_file`, `edit_file`, `list_directory`, `current_path`, `search_file`, and `run_command`
- **Permission Mode**: Can operate in `auto` (all tools allowed) or `permission` (user must approve each write/exec tool)
- **Session Management**: Create, list, and switch between DeepSeek chat sessions
- **Workspace Context**: Configurable workspace directory for all file operations

### UI Features
- **Conversation View**: Displays agent messages, tool executions, and results. Supports Rich `Text` objects and Rich markup parsing for styled output.
- **Command System**: Built-in commands:
  - `/clear` — Clear the conversation
  - `/help` — Show available commands
  - `/new` — Start a new conversation
  - `/settings` — Display current settings
  - `/quit` — Exit the application
  - `/mode` — Set operation mode (auto/permission)
  - `/set_workspace <path>` — Set the workspace directory
  - `/change_chat <number>` — Switch to a chat session by number
  - `/chats` — List all chat sessions with their IDs and titles
- **Command Suggestions**: Dropdown autocomplete for slash commands. Shows at least 4 visible commands, navigable with arrow keys, selectable with Enter/Tab. Compact single-row layout for maximum visibility.
- **Centralized Theme**: All colors defined in `app/theme/__init__.py`. Purple accent (#C792EA) for commands, white text on dark backgrounds, consistent border styling.
- **Status Bar**: Shows elapsed time with animated spinner during agent processing
- **Permission Selector**: Interactive allow once / allow for session / reject UI for tool permissions
- **Multi-threaded**: Agent runs in background threads, keeping the UI responsive

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13+ |
| TUI Framework | Textual |
| HTTP Client | Requests |
| Rich Text | Rich (Text objects, markup) |
| API | DeepSeek Chat API (SSE streaming) |
| Build System | PyInstaller |
| WASM Runtime | wasmtime (for PoW challenge solving) |

## Theme System

All UI colors are centralized in `app/theme/__init__.py`:

| Constant | Value | Usage |
|----------|-------|-------|
| `ACCENT` | `#C792EA` | Commands, diamond symbol, highlights |
| `BG_MAIN` | `#000000` | Main app background |
| `BG_WIDGET` | `#1A1A1A` | Widget/card backgrounds |
| `BG_INPUT` | `#292929` | Input box background |
| `TEXT_PRIMARY` | `#FFFFFF` | Primary white text |
| `TEXT_SECONDARY` | `#A0A0A0` | Footer, status bar |
| `TEXT_MUTED` | `#DCDCDC` | System messages |
| `BORDER_LIGHT` | `rgba(255,255,255,0.08)` | Subtle borders |
| `BORDER_MEDIUM` | `rgba(255,255,255,0.2)` | Visible borders |
| `LOGO_GRADIENT` | Blue→Purple list | Logo gradient colors |

Widgets import from `app.theme` rather than hardcoding colors, ensuring visual consistency.

## How It Works

1. **Initialization**: Loads API credentials from `.env` file, creates a DeepSeek chat session
2. **System Prompt**: Sends a comprehensive system prompt defining the agent's behavior, tool usage protocol, and JSON output format
3. **User Input**: User types a natural language request in the terminal
4. **Agent Loop**:
   - Sends prompt to DeepSeek API via SSE streaming
   - Parses the streaming JSON response to extract status and tool actions
   - Executes requested tools (with optional permission checks)
   - Feeds tool results back to the model
   - Repeats until the agent signals `finished`
5. **Tool Execution**: All file operations are scoped to the configured workspace directory

## Setup

1. Install dependencies: `pip install -r app/agent/requirements.txt`
2. Create a `.env` file with DeepSeek credentials:
   - `DS_SMIDV2`
   - `DS_SESSION_ID`
   - `DS_AUTHORIZATION`
3. Run: `python main.py`

## Build (Windows Executable)

```
pyinstaller DeepSeekCli.spec
```

Outputs a standalone `DeepSeekCli.exe` in the `dist/` directory.
