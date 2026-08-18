"""Tool execution display formatting for the conversation view.

Produces styled Rich Text objects for two moments of a tool call:

* RUNNING  - shown while the tool executes (with a spinner frame).
* DONE     - shown when the tool finishes (success / error), optionally
             followed by a dim secondary detail block (command output,
             diff excerpt, grep hits ...).

Design principles:
  - Compact: one main line + optional 2-4 dim detail lines.
  - Informative: most relevant argument before, most relevant outcome after.
  - Themed: centralized color tokens from app.theme.
  - Extensible: register a tool in TOOL_DISPLAY and add a formatter.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from rich.text import Text

from app.theme import (
    ACCENT_RGB,
    TEXT_MUTED_RGB,
    SUCCESS,
    ERROR,
)

# ---------------------------------------------------------------------------
# Tool display registry (safe BMP glyphs only - legacy codepage friendly)
# ---------------------------------------------------------------------------

TOOL_DISPLAY: Dict[str, Dict[str, str]] = {
    "read_file":                {"icon": "\u25B8", "name": "ReadFile"},
    "write_file":               {"icon": "\u270E", "name": "WriteFile"},
    "replace":                  {"icon": "\u2194", "name": "Replace"},
    "list_directory":           {"icon": "\u2263", "name": "ListDir"},
    "run_shell_command":        {"icon": "\u276F", "name": "RunCommand"},
    "run_command":              {"icon": "\u276F", "name": "RunCommand"},
    "code_interpreter":         {"icon": "\u03BB", "name": "CodeExec"},
    "glob":                     {"icon": "\u25C8", "name": "Glob"},
    "search_file":              {"icon": "\u25C8", "name": "SearchFile"},
    "grep_search":              {"icon": "\u2315", "name": "GrepSearch"},
    "current_path":             {"icon": "\u2316", "name": "CurrentPath"},
    "google_web_search":        {"icon": "\u2604", "name": "WebSearch"},
    "web_fetch":                {"icon": "\u2604", "name": "WebFetch"},
    "list_background_processes":{"icon": "\u2630", "name": "BgProcesses"},
    "read_background_output":   {"icon": "\u2630", "name": "BgOutput"},
    "kill_process":             {"icon": "\u2716", "name": "KillProcess"},
    "enter_plan_mode":          {"icon": "\u270D", "name": "PlanMode"},
    "ask_user":                 {"icon": "\u003F", "name": "AskUser"},
    "user_response":            {"icon": "\u2726", "name": "Response"},
}

_SEPARATOR = " \u00B7 "  # " · "
_NAME_STYLE = f"bold {ACCENT_RGB}"
_DETAIL_STYLE = f"dim {TEXT_MUTED_RGB}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_display(tool: str) -> Dict[str, str]:
    """Return display config for a tool, falling back to the raw name."""
    return TOOL_DISPLAY.get(tool, {"icon": "\u25B8", "name": tool})


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate a string to *max_len* characters, appending ellipsis."""
    text = text.rstrip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


def _brief_output(text: str, max_len: int = 120) -> str:
    """Return a single-line brief summary of potentially multi-line output."""
    if not text:
        return ""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return ""
    first = lines[0]
    if len(first) > max_len:
        first = first[: max_len - 1] + "\u2026"
    if len(lines) > 1:
        return f"{first} (+{len(lines) - 1} more lines)"
    return first


def _fmt_duration(seconds: Optional[float]) -> str:
    """Human friendly duration string."""
    if seconds is None:
        return ""
    if seconds < 0.05:
        return "<50ms"
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    return f"{minutes}m{seconds - minutes * 60:.0f}s"


# ---------------------------------------------------------------------------
# BEFORE / RUNNING detail formatters  (arguments of the invocation)
# ---------------------------------------------------------------------------

def _before_read_file(args: dict) -> str:
    path = args.get("path", "")
    start = args.get("start_line")
    end = args.get("end_line")
    if start and end:
        return f"{path} ({start}-{end})"
    if start:
        return f"{path} (from line {start})"
    return path


def _before_write_file(args: dict) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    lines = content.count("\n") + (1 if content else 0)
    return f"{path} ({lines} lines)"


def _before_replace(args: dict) -> str:
    path = args.get("path", "")
    search = args.get("search", "")
    preview = _truncate(search.split("\n")[0].strip(), 40) if search else ""
    return f"{path}" + (f" \u00AB{preview}\u00BB" if preview else "")


def _before_run_command(args: dict) -> str:
    cmd = args.get("command", "")
    bg = args.get("background", False)
    prefix = "[bg] " if bg else ""
    return f"{prefix}{_truncate(cmd, 100)}"


def _before_grep_search(args: dict) -> str:
    pattern = args.get("pattern", "")
    path = args.get("path", "")
    include = args.get("include", "")
    parts = [f'"{_truncate(pattern, 40)}"']
    if path:
        parts.append(f"in {path}")
    if include:
        parts.append(f"[{include}]")
    return " ".join(parts)


def _before_glob(args: dict) -> str:
    pattern = args.get("pattern", "*")
    path = args.get("path", "")
    return f"{pattern}" + (f" in {path}" if path else "")


def _before_code_interpreter(args: dict) -> str:
    code = args.get("code", "")
    first_line = code.strip().split("\n")[0].strip() if code else ""
    return _truncate(first_line, 80)


def _before_web_search(args: dict) -> str:
    return f'"{args.get("query", "")}"'


def _before_web_fetch(args: dict) -> str:
    return args.get("url", "")


def _before_plan_mode(args: dict) -> str:
    plan = args.get("plan", True)
    if isinstance(plan, str):
        plan = plan.lower() in ("true", "1", "yes")
    return "ON" if plan else "OFF"


def _before_id_arg(args: dict) -> str:
    return args.get("id", "")


def _before_list_dir(args: dict) -> str:
    return args.get("path", ".")


def _before_default(args: dict) -> str:
    """Fallback: show first non-empty argument value."""
    for v in args.values():
        if v:
            return _truncate(str(v), 80)
    return ""


_BEFORE_FORMATTERS = {
    "read_file": _before_read_file,
    "write_file": _before_write_file,
    "replace": _before_replace,
    "run_shell_command": _before_run_command,
    "run_command": _before_run_command,
    "grep_search": _before_grep_search,
    "glob": _before_glob,
    "search_file": _before_glob,
    "code_interpreter": _before_code_interpreter,
    "google_web_search": _before_web_search,
    "web_fetch": _before_web_fetch,
    "enter_plan_mode": _before_plan_mode,
    "read_background_output": _before_id_arg,
    "kill_process": _before_id_arg,
    "list_directory": _before_list_dir,
}


def _before_detail(tool: str, args: dict) -> str:
    formatter = _BEFORE_FORMATTERS.get(tool, _before_default)
    return formatter(args)


# ---------------------------------------------------------------------------
# AFTER summaries  (one-line outcome of the result)
# ---------------------------------------------------------------------------

def _after_read_file(result: dict) -> str:
    r = result.get("result", {})
    total = r.get("total_lines", "?")
    start = r.get("start_line", 1)
    end = r.get("end_line", "?")
    truncated = r.get("truncated", False)
    return f"lines {start}-{end} of {total}" + (" (truncated)" if truncated else "")


def _after_write_file(result: dict) -> str:
    r = result.get("result", {})
    path = r.get("path", "")
    return f"written {path}" if path else "written"


def _after_replace(result: dict) -> str:
    r = result.get("result", {})
    match_type = r.get("match_type", "?")
    confidence = r.get("confidence", 0)
    added = r.get("lines_added", 0)
    removed = r.get("lines_removed", 0)
    parts = [f"{match_type} {confidence:.0%}"]
    if added or removed:
        parts.append(f"+{added}/-{removed}")
    return " ".join(parts)


def _after_run_command(result: dict) -> str:
    r = result.get("result", {})
    bg_id = r.get("background_id")
    if bg_id:
        return f"background {bg_id}"
    rc = r.get("returncode", "?")
    if rc == 0:
        out = _brief_output(r.get("stdout", ""), 60)
        return "exit 0" + (f" \u00B7 {out}" if out else "")
    err = _brief_output(r.get("stderr", "") or r.get("stdout", ""), 60)
    return f"exit {rc}" + (f" \u00B7 {err}" if err else "")


def _after_grep_search(result: dict) -> str:
    n = len(result.get("result", {}).get("results", []))
    return f"{n} matches"


def _after_glob(result: dict) -> str:
    n = len(result.get("result", {}).get("matches", []))
    return f"{n} files"


def _after_code_interpreter(result: dict) -> str:
    r = result.get("result", {})
    rc = r.get("returncode", "?")
    if rc == 0:
        out = _brief_output(r.get("stdout", ""), 60)
        return "exit 0" + (f" \u00B7 {out}" if out else "")
    err = _brief_output(r.get("stderr", "") or r.get("stdout", ""), 60)
    return f"exit {rc}" + (f" \u00B7 {err}" if err else "")


def _after_web_search(result: dict) -> str:
    n = len(result.get("result", {}).get("results", []))
    return f"{n} results"


def _after_web_fetch(result: dict) -> str:
    r = result.get("result", {})
    return f"HTTP {r.get('status_code', '?')} \u00B7 {len(r.get('content', ''))} chars"


def _after_list_dir(result: dict) -> str:
    n = len(result.get("result", {}).get("entries", []))
    return f"{n} entries"


def _after_current_path(result: dict) -> str:
    return result.get("result", {}).get("path", "")


def _after_plan_mode(result: dict) -> str:
    return f"plan mode {result.get('result', {}).get('mode', '?')}"


def _after_bg_processes(result: dict) -> str:
    r = result.get("result", {})
    return f"{len(r.get('processes', []))} shown, {r.get('tracked_count', 0)} tracked"


def _after_bg_output(result: dict) -> str:
    r = result.get("result", {})
    status = r.get("status", "?")
    brief = _brief_output(r.get("output", ""), 60)
    return status + (f" \u00B7 {brief}" if brief else "")


def _after_kill_process(result: dict) -> str:
    return result.get("result", {}).get("message", "done")


def _after_default(result: dict) -> str:
    return result.get("status", "?")


_AFTER_FORMATTERS = {
    "read_file": _after_read_file,
    "write_file": _after_write_file,
    "replace": _after_replace,
    "run_shell_command": _after_run_command,
    "run_command": _after_run_command,
    "grep_search": _after_grep_search,
    "glob": _after_glob,
    "search_file": _after_glob,
    "code_interpreter": _after_code_interpreter,
    "google_web_search": _after_web_search,
    "web_fetch": _after_web_fetch,
    "list_directory": _after_list_dir,
    "current_path": _after_current_path,
    "enter_plan_mode": _after_plan_mode,
    "list_background_processes": _after_bg_processes,
    "read_background_output": _after_bg_output,
    "kill_process": _after_kill_process,
}


# ---------------------------------------------------------------------------
# Detail block builders  (dim secondary lines under the main line)
# ---------------------------------------------------------------------------

def _detail_lines_block(lines, max_lines: int, style: str) -> Optional[Text]:
    """Render a list of (text, style) or plain str lines as a dim block."""
    if not lines:
        return None
    shown = lines[:max_lines]
    extra = len(lines) - len(shown)
    text = Text()
    for i, item in enumerate(shown):
        if i:
            text.append("\n")
        text.append("\u2502 ", style=_DETAIL_STYLE)  # │
        if isinstance(item, tuple):
            content, item_style = item
        else:
            content, item_style = item, style
        text.append(_truncate(content, 100), style=item_style)
    if extra > 0:
        text.append("\n")
        text.append(f"\u2502 \u2026 +{extra} more lines", style=_DETAIL_STYLE)
    return text


def _detail_run_command(result: dict) -> Optional[Text]:
    r = result.get("result", {})
    rc = r.get("returncode")
    if r.get("background_id"):
        return None
    if rc == 0:
        out = r.get("stdout", "")
        lines = [l for l in out.splitlines() if l.strip()]
        return _detail_lines_block(lines, 3, _DETAIL_STYLE)
    err = r.get("stderr", "") or r.get("stdout", "")
    lines = [l for l in err.splitlines() if l.strip()]
    return _detail_lines_block(lines, 3, f"dim {ERROR}")


def _detail_replace(result: dict) -> Optional[Text]:
    diff = result.get("result", {}).get("diff_preview") or ""
    lines = []
    for l in diff.splitlines():
        if l.startswith("+++") or l.startswith("---"):
            continue
        if l.startswith("+"):
            lines.append((l, f"dim {SUCCESS}"))
        elif l.startswith("-"):
            lines.append((l, f"dim {ERROR}"))
    return _detail_lines_block(lines, 4, _DETAIL_STYLE)


def _detail_grep_search(result: dict) -> Optional[Text]:
    results = result.get("result", {}).get("results", [])
    lines = [
        f"{r.get('file', '')}:{r.get('line', '')}  {r.get('content', '').strip()}"
        for r in results
    ]
    return _detail_lines_block(lines, 3, _DETAIL_STYLE)


def _detail_list_dir(result: dict) -> Optional[Text]:
    entries = result.get("result", {}).get("entries", [])
    if len(entries) <= 12:
        return None  # small listings are fine inline in the summary
    return _detail_lines_block(sorted(entries), 4, _DETAIL_STYLE)


_DETAIL_FORMATTERS = {
    "run_shell_command": _detail_run_command,
    "run_command": _detail_run_command,
    "code_interpreter": _detail_run_command,
    "replace": _detail_replace,
    "grep_search": _detail_grep_search,
    "list_directory": _detail_list_dir,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_tool_running(tool: str, args: dict, spinner: str = "\u28B3") -> Text:
    """Styled line shown while a tool is executing.

    Layout: ``<spinner> <ToolName> · <arguments>``
    """
    display = _get_display(tool)
    detail = _before_detail(tool, args)

    text = Text()
    text.append(f"{spinner} ", style=_NAME_STYLE)
    text.append(display["name"], style=_NAME_STYLE)
    if detail:
        text.append(_SEPARATOR, style=_DETAIL_STYLE)
        text.append(detail, style=_DETAIL_STYLE)
    return text


def format_tool_done(
    tool: str,
    args: dict,
    result: dict,
    duration: Optional[float] = None,
) -> Tuple[Text, Optional[Text]]:
    """Styled lines shown after a tool finished.

    Returns (main_line, optional_detail_block).

    Success layout: ``✓ <ToolName> · <arguments> · <outcome> · <duration>``
    Error layout:   ``✗ <ToolName> · <arguments> — <error> · <duration>``
    """
    display = _get_display(tool)
    name = display["name"]
    before = _before_detail(tool, args)
    is_error = result.get("status") == "error"
    dur = _fmt_duration(duration)

    main = Text()
    detail_block: Optional[Text] = None

    if is_error:
        # Unified error extraction: 'result.error_msg' or 'error.message'.
        err_block = result.get("result") or {}
        err_obj = result.get("error") or {}
        message = str(
            err_block.get("error_msg")
            or err_obj.get("message")
            or "error"
        )
        main.append("\u2717 ", style=f"bold {ERROR}")
        main.append(name, style=f"bold {ERROR}")
        if before:
            main.append(_SEPARATOR, style=_DETAIL_STYLE)
            main.append(before, style=_DETAIL_STYLE)
        main.append(" \u2014 ", style=f"dim {ERROR}")
        main.append(_truncate(message, 120), style=f"dim {ERROR}")
        if dur:
            main.append(_SEPARATOR, style=_DETAIL_STYLE)
            main.append(dur, style=_DETAIL_STYLE)
        return main, None

    # Success
    formatter = _AFTER_FORMATTERS.get(tool, _after_default)
    outcome = formatter(result)

    main.append("\u2713 ", style=f"bold {SUCCESS}")
    main.append(name, style=f"bold {SUCCESS}")
    if before:
        main.append(_SEPARATOR, style=_DETAIL_STYLE)
        main.append(before, style=_DETAIL_STYLE)
    if outcome:
        main.append(_SEPARATOR, style=_DETAIL_STYLE)
        main.append(outcome, style=_DETAIL_STYLE)
    if dur:
        main.append(_SEPARATOR, style=_DETAIL_STYLE)
        main.append(dur, style=f"dim italic {TEXT_MUTED_RGB}")

    # Optional detail block for richer context
    detail_formatter = _DETAIL_FORMATTERS.get(tool)
    if detail_formatter is not None:
        try:
            detail_block = detail_formatter(result)
        except Exception:
            detail_block = None

    return main, detail_block


# ---------------------------------------------------------------------------
# Backwards-compatible helpers
# ---------------------------------------------------------------------------

def format_tool_before(tool: str, args: dict) -> Text:
    """Compatibility wrapper (static, no spinner)."""
    return format_tool_running(tool, args, spinner=_get_display(tool)["icon"])


def format_tool_after(tool: str, args: dict, result: dict) -> Text:
    """Compatibility wrapper returning only the main line."""
    main, _ = format_tool_done(tool, args, result)
    return main
