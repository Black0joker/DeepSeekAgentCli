"""Centralized file-backed logging for the DeepSeekCli agent.

This module keeps the legacy static Logger interface used across the
codebase, but routes all records through Python's standard logging
machinery with rotating file handlers. In addition to the main
agent.log, warnings and errors are written to dedicated files so
they are easy to find and triage.
"""

import datetime
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

if getattr(sys, 'frozen', False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent.parent.parent


class _WarningOnlyFilter(logging.Filter):
    """Allow only WARNING records through, excluding ERROR and CRITICAL."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == logging.WARNING


class Logger:
    """Static logging facade for the agent and UI layers."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    BLUE = "\033[38;5;75m"     # #58a6ff
    GREEN = "\033[38;5;78m"    # #3fb950
    YELLOW = "\033[38;5;214m"  # #d29922
    RED = "\033[38;5;203m"     # #f85149
    CYAN = "\033[38;5;141m"    # #bc8cff
    MAGENTA = "\033[38;5;177m" # #d2a8ff
    GRAY = "\033[38;5;245m"    # gray for args

    LOG_DIR = _BASE / "logs"
    LOG_FILE = LOG_DIR / "agent.log"
    ERROR_LOG_FILE = LOG_DIR / "errors.log"
    WARN_LOG_FILE = LOG_DIR / "warnings.log"
    TOOL_LOG_FILE = LOG_DIR / "tool_calls.log"

    _configured = False
    _LOGGER = logging.getLogger("warriorx.agent")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @classmethod
    def _configure(cls) -> None:
        """Configure logging handlers once at runtime."""
        if cls._configured:
            return

        try:
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            # If the log directory cannot be created, logging will silently
            # fall back to stderr through the existing print calls.
            pass

        cls._LOGGER.setLevel(logging.DEBUG)
        cls._LOGGER.propagate = False

        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] "
            "[%(module)s:%(funcName)s:%(lineno)d] %(message)s"
        )

        # Main rotating log: everything from DEBUG and above.
        main_handler = RotatingFileHandler(
            cls.LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(fmt)
        cls._LOGGER.addHandler(main_handler)

        # Dedicated warning log (warnings only, not errors).
        warn_handler = RotatingFileHandler(
            cls.WARN_LOG_FILE,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        warn_handler.setLevel(logging.WARNING)
        warn_handler.addFilter(_WarningOnlyFilter())
        warn_handler.setFormatter(fmt)
        cls._LOGGER.addHandler(warn_handler)

        # Dedicated error log.
        error_handler = RotatingFileHandler(
            cls.ERROR_LOG_FILE,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(fmt)
        cls._LOGGER.addHandler(error_handler)

        cls._configured = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _timestamp() -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _log(cls, level: int, message: str, prefix: str = "") -> None:
        """Log a message to all configured file handlers and the console."""
        cls._configure()
        try:
            # stacklevel=3: Logger.<level> -> Logger._log -> logging call.
            cls._LOGGER.log(level, message, stacklevel=3)
        except Exception:
            pass

        try:
            print(f"{prefix} [{cls._timestamp()}] {message}")
        except Exception:
            pass

    @classmethod
    def _log_file_only(cls, level: int, message: str) -> None:
        """Log to files only; used where the console already has custom output."""
        cls._configure()
        try:
            cls._LOGGER.log(level, message, stacklevel=3)
        except Exception:
            pass

    @classmethod
    def _write_tool_log(cls, entry: dict) -> None:
        """Append a structured tool call/result entry to tool_calls.log."""
        try:
            cls.TOOL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with cls.TOOL_LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[LOG ERROR] Could not write to tool log file: {e}")

    # ------------------------------------------------------------------
    # Standard levels
    # ------------------------------------------------------------------

    @classmethod
    def info(cls, message: str) -> None:
        cls._log(logging.INFO, message, f"{cls.BLUE}[*]{cls.RESET}")

    @classmethod
    def success(cls, message: str) -> None:
        cls._log(logging.INFO, message, f"{cls.GREEN}[+]{cls.RESET}")

    @classmethod
    def warn(cls, message: str) -> None:
        cls._log(logging.WARNING, message, f"{cls.YELLOW}[!]{cls.RESET}")

    @classmethod
    def warning(cls, message: str) -> None:
        cls.warn(message)

    @classmethod
    def error(cls, message: str) -> None:
        cls._log(logging.ERROR, message, f"{cls.RED}[x]{cls.RESET}")

    @classmethod
    def critical(cls, message: str) -> None:
        cls._log(logging.CRITICAL, message, f"{cls.RED}[!]{cls.RESET}")

    @classmethod
    def debug(cls, message: str) -> None:
        cls._log(logging.DEBUG, message, f"{cls.GRAY}[D]{cls.RESET}")

    @classmethod
    def exception(cls, message: str) -> None:
        """Log an exception message with the full traceback to files.

        This method is used inside except blocks (for example in
        AgentWrapper) and therefore captures the active exception
        automatically.
        """
        cls._configure()
        try:
            cls._LOGGER.error(message, exc_info=True, stacklevel=2)
        except Exception:
            pass

        try:
            print(f"{cls.RED}[x]{cls.RESET} [{cls._timestamp()}] {message}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tool logging
    # ------------------------------------------------------------------

    @classmethod
    def tool(cls, tool_name: str, args: dict) -> None:
        """Log a tool invocation with full arguments to console and files."""
        display_names = {
            "read_file": "ReadFile",
            "list_directory": "ListDir",
            "replace": "EditFile",
            "write_file": "WriteFile",
            "run_shell_command": "RunShellCmd",
            "current_path": "CurrentPath",
            "search_file": "SearchFile",
            "glob": "Glob",
            "grep_search": "GrepSearch",
            "ask_user": "AskUser",
            "user_response": "UserResponse",
            "list_background_processes": "ListBgProcs",
            "read_background_output": "ReadBgOutput",
            "kill_process": "KillProcess",
            "enter_plan_mode": "EnterPlanMode",
            "google_web_search": "WebSearch",
            "web_fetch": "WebFetch",
            "code_interpreter": "CodeInterpreter",
        }

        display = display_names.get(tool_name, tool_name)

        # Build concise display message based on tool type.
        if tool_name == "run_shell_command":
            msg = args.get("command", "<no command>")
            extra_parts = []
            if args.get("cwd"):
                extra_parts.append(f"cwd={args['cwd']}")
            if args.get("timeout"):
                extra_parts.append(f"timeout={args['timeout']}")
            if args.get("background"):
                extra_parts.append("BG=true")
            if extra_parts:
                msg += f" ({', '.join(extra_parts)})"
        elif tool_name == "grep_search":
            pattern = args.get("pattern", "<no pattern>")
            path = args.get("path", ".")
            include = args.get("include", "*")
            msg = f"pattern='{pattern}' in {path} (include={include})"
        elif tool_name == "glob":
            msg = f"pattern='{args.get('pattern', '<no pattern>')}' in {args.get('path', '.')}"
        elif tool_name == "replace":
            path = args.get("path", "<no path>")
            search = args.get("search", "")
            replace = args.get("replace", "")
            search_preview = (search[:60] + "...") if len(search) > 60 else search
            replace_preview = (replace[:60] + "...") if len(replace) > 60 else replace
            msg = f"{path} | '{search_preview}' -> '{replace_preview}'"
        elif tool_name == "write_file":
            path = args.get("path", "<no path>")
            content_len = len(args.get("content", ""))
            msg = f"{path} ({content_len} chars)"
        elif tool_name in ("list_directory", "read_file", "current_path", "search_file"):
            msg = args.get("path", ".")
        elif tool_name == "read_background_output":
            msg = f"id={args.get('id', '<unknown>')}"
        elif tool_name == "kill_process":
            msg = f"id={args.get('id', '<unknown>')}"
        elif tool_name == "google_web_search":
            msg = f"query='{args.get('query', '<no query>')}'"
        elif tool_name == "web_fetch":
            msg = args.get("url", "<no url>")
        elif tool_name == "ask_user":
            question = args.get("question", "")
            msg = (question[:80] + "...") if len(question) > 80 else question
        elif tool_name == "user_response":
            desc = args.get("description", "")
            msg = (desc[:80] + "...") if len(desc) > 80 else desc
        elif tool_name == "list_background_processes":
            msg = "(list all)"
        elif tool_name == "enter_plan_mode":
            plan_value = args.get('plan', True)
            if isinstance(plan_value, str):
                plan_value = plan_value.lower() in ('true', '1', 'yes')
            msg = "(enter read-only mode)" if plan_value else "(exit read-only mode)"
        else:
            msg = json.dumps(args, ensure_ascii=False)

        args_str = json.dumps(args, ensure_ascii=False)

        # Console output (preserves legacy format).
        try:
            check = f"{cls.GREEN}\u2713{cls.RESET}"
            print(f"{check} {cls.BOLD}{display}{cls.RESET} {cls.CYAN}{msg}{cls.RESET}")
            print(f"  {cls.GRAY}Args: {args_str}{cls.RESET} [{cls._timestamp()}]")
        except Exception:
            pass

        # General file log.
        cls._log_file_only(
            logging.INFO,
            f"TOOL {display}: {msg} | Args: {args_str}",
        )

        # Structured tool call log.
        cls._write_tool_log({
            "timestamp": cls._timestamp(),
            "tool": tool_name,
            "display_name": display,
            "arguments": args,
            "summary": msg,
        })

    @classmethod
    def tool_result(cls, tool_name: str, result: dict) -> None:
        """Log the result of a tool execution."""
        status = result.get("status", "unknown")
        display_names = {
            "read_file": "ReadFile",
            "list_directory": "ListDir",
            "replace": "EditFile",
            "write_file": "WriteFile",
            "run_shell_command": "RunShellCmd",
            "current_path": "CurrentPath",
            "search_file": "SearchFile",
            "glob": "Glob",
            "grep_search": "GrepSearch",
            "list_background_processes": "ListBgProcs",
            "read_background_output": "ReadBgOutput",
            "kill_process": "KillProcess",
            "google_web_search": "WebSearch",
            "web_fetch": "WebFetch",
            "code_interpreter": "CodeInterpreter",
        }
        display = display_names.get(tool_name, tool_name)

        if status == "success":
            icon = f"{cls.GREEN}\u2713{cls.RESET}"
            level = logging.INFO
        else:
            icon = f"{cls.RED}\u2717{cls.RESET}"
            level = logging.ERROR

        result_summary = json.dumps(result.get("result", {}), ensure_ascii=False)
        if len(result_summary) > 200:
            result_summary = result_summary[:200] + "..."

        try:
            print(
                f"  {icon} {cls.BOLD}{display} Result{cls.RESET}: "
                f"{result_summary} [{cls._timestamp()}]"
            )
        except Exception:
            pass

        cls._log_file_only(
            level,
            f"TOOL_RESULT {display}: status={status} | {result_summary}",
        )

        # Structured tool result log.
        cls._write_tool_log({
            "timestamp": cls._timestamp(),
            "type": "result",
            "tool": tool_name,
            "display_name": display,
            "status": status,
            "result_summary": result_summary,
        })
