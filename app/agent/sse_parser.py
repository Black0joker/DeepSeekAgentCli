"""
SSE Parser for DeepSeek API responses.

Accumulates the full RESPONSE content from the SSE stream,
then parses it as JSON and yields structured events.

Supports both protocols:
- normal: conversation_mode exists in initial response
- thinking: no conversation_mode

Yields:
- {"type": "message_id", "value": int}
- {"type": "status", "value": str}
- {"type": "action", "value": dict}
- {"type": "thinking_delta", "value": str}   (streamed THINK fragment chunk)
- {"type": "thinking_done", "value": True}   (THINK fragment finished)
- {"type": "response_delta", "value": str, "tool": str}
    (streamed user_response/ask_user text while the JSON is still arriving)
"""
import json
import re
from typing import Any, Dict, Generator, Iterable


# Tools whose text payload (description/question) is streamed to the UI
# while the JSON response is still arriving.
_RESPONSE_TOOL_FIELDS = (
    (re.compile(r'"tool"\s*:\s*"user_response"'), "user_response", "description"),
    (re.compile(r'"tool"\s*:\s*"ask_user"'), "ask_user", "question"),
)

_STRING_ESCAPES = {
    '"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t",
    "r": "\r", "b": "\b", "f": "\f",
}


def _extract_partial_string_field(content: str, field: str):
    """Extract the (possibly incomplete) value of ``"<field>": "..."`` from
    progressively accumulated JSON text.

    Returns None while the field has not started. Once the opening quote is
    seen, returns the decoded text so far; it stays partial until the closing
    quote arrives. Escape sequences are decoded; a trailing incomplete escape
    is excluded so no character is ever emitted twice.
    """
    m = re.search(r'"' + re.escape(field) + r'"\s*:\s*"', content)
    if not m:
        return None
    i = m.end()
    out = []
    n = len(content)
    while i < n:
        ch = content[i]
        if ch == '"':
            break  # closing quote: value complete
        if ch == "\\":
            if i + 1 >= n:
                break  # trailing backslash: incomplete escape
            esc = content[i + 1]
            if esc == "u":
                hexdigits = content[i + 2:i + 6]
                if len(hexdigits) < 4:
                    break  # incomplete \uXXXX escape
                try:
                    cp = int(hexdigits, 16)
                except ValueError:
                    break
                if 0xD800 <= cp <= 0xDBFF:
                    # High surrogate: wait for the low surrogate to arrive
                    if content[i + 6:i + 8] != "\\u":
                        break
                    low_hex = content[i + 8:i + 12]
                    if len(low_hex) < 4:
                        break
                    try:
                        low = int(low_hex, 16)
                    except ValueError:
                        break
                    if not (0xDC00 <= low <= 0xDFFF):
                        break
                    combined = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00)
                    out.append(chr(combined))
                    i += 12
                    continue
                out.append(chr(cp))
                i += 6
                continue
            if esc in _STRING_ESCAPES:
                out.append(_STRING_ESCAPES[esc])
                i += 2
                continue
            # Unknown escape: pass the escaped char through
            out.append(esc)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _stream_response_deltas(content: str, state: dict):
    """Detect a user_response/ask_user action in the accumulating JSON and
    progressively yield its text payload (description/question) as
    ``response_delta`` events until the JSON string ends.

    ``state`` tracks detection and emission progress across calls:
    {"tool": str|None, "field": str|None, "emitted": int}
    """
    if state.get("tool") is None:
        for regex, tool_name, field in _RESPONSE_TOOL_FIELDS:
            if regex.search(content):
                state["tool"] = tool_name
                state["field"] = field
                break
        else:
            return
    partial = _extract_partial_string_field(content, state["field"])
    if partial is None:
        return
    emitted = state.get("emitted", 0)
    if len(partial) > emitted:
        yield {
            "type": "response_delta",
            "value": partial[emitted:],
            "tool": state["tool"],
        }
        state["emitted"] = len(partial)


def parse_sse(lines: Iterable[str]) -> Generator[Dict[str, Any], None, None]:
    """
    Parse SSE stream lines from DeepSeek API response.

    Args:
        lines: Iterable of SSE lines (e.g., response.iter_lines(decode_unicode=True))

    Yields:
        Dicts with 'type' and 'value' keys:
        - {"type": "message_id", "value": int}
        - {"type": "status", "value": str}
        - {"type": "action", "value": dict}
    """
    message_sent = False
    protocol = None          # "normal" | "thinking"
    collecting = False
    content = ""
    last_fragment_type = None   # "THINK" | "RESPONSE" | None
    thinking_active = False
    # Streaming state for user_response/ask_user text payloads
    stream_state = {"tool": None, "field": None, "emitted": 0}

    for line in lines:
        if not line or not line.startswith("data: "):
            continue

        try:
            obj = json.loads(line[6:])
        except json.JSONDecodeError:
            continue

        if obj.get("type") == "error":
            err_value = (
                obj.get("content")
                or obj.get("v")
                or obj.get("error")
                or "Unknown API error"
            )
            yield {"type": "error", "value": err_value}
            return
        # ------------------------------------------------------
        # Initial response: detect protocol and get message_id
        # ------------------------------------------------------
        if (
            not message_sent
            and isinstance(obj.get("v"), dict)
            and "response" in obj["v"]
        ):
            response_obj = obj["v"]["response"]
            protocol = (
                "normal"
                if "conversation_mode" in response_obj
                else "thinking"
            )
            message_id = response_obj.get("message_id")
            if message_id is not None:
                message_sent = True
                yield {
                    "type": "message_id",
                    "value": message_id,
                }
            # Normal protocol may already contain a THINK or RESPONSE fragment.
            if protocol == "normal":
                fragments = response_obj.get("fragments", [])
                if fragments:
                    last = fragments[-1]
                    last_fragment_type = last.get("type")
                    if last_fragment_type == "RESPONSE":
                        collecting = True
                        content = last.get("content", "")
                        if content:
                            yield from _stream_response_deltas(content, stream_state)
                    elif last_fragment_type == "THINK":
                        thinking_active = True
                        initial = last.get("content", "")
                        if initial:
                            yield {"type": "thinking_delta", "value": initial}
            continue

        # ------------------------------------------------------
        # Check for stream end
        # ------------------------------------------------------
        if (
            obj.get("p") == "response/status"
            and obj.get("o") == "SET"
            and obj.get("v") == "FINISHED"
        ):
            break

        # ------------------------------------------------------
        # NORMAL PROTOCOL: accumulate RESPONSE content
        # ------------------------------------------------------
        if protocol == "normal":
            if (
                obj.get("p") == "response/fragments"
                and obj.get("o") == "APPEND"
            ):
                fragments = obj.get("v", [])
                if fragments:
                    new_last = fragments[-1]
                    new_type = new_last.get("type")
                    prev_type = last_fragment_type
                    last_fragment_type = new_type
                    if new_type == "RESPONSE":
                        collecting = True
                        content = new_last.get("content", "")
                        if content:
                            yield from _stream_response_deltas(content, stream_state)
                        if prev_type == "THINK" and thinking_active:
                            thinking_active = False
                            yield {"type": "thinking_done", "value": True}
                    elif new_type == "THINK":
                        thinking_active = True
                        initial = new_last.get("content", "")
                        if initial:
                            yield {"type": "thinking_delta", "value": initial}
            else:
                path = obj.get("p")
                value = obj.get("v")
                if path == "response/fragments/-1/content":
                    if thinking_active:
                        if isinstance(value, str) and value:
                            yield {"type": "thinking_delta", "value": value}
                    elif collecting and isinstance(value, str):
                        content += value
                        yield from _stream_response_deltas(content, stream_state)
                elif path is None and isinstance(value, str):
                    if thinking_active:
                        yield {"type": "thinking_delta", "value": value}
                    elif collecting:
                        content += value
                        yield from _stream_response_deltas(content, stream_state)
                # Other paths (elapsed_secs, BATCH, etc.) are ignored

        # ------------------------------------------------------
        # THINKING PROTOCOL: accumulate content
        # ------------------------------------------------------
        elif protocol == "thinking":
            path = obj.get("p")
            if path == "response/thinking_content":
                collecting = False
                continue
            if path == "response/content":
                collecting = True
            elif path is not None:
                collecting = False
            if not collecting:
                continue
            value = obj.get("v")
            if not isinstance(value, str):
                continue
            content += value
            yield from _stream_response_deltas(content, stream_state)

    # ----------------------------------------------------------
    # Parse the accumulated content
    # ----------------------------------------------------------
    if not content:
        return

    # Strip markdown code fences (```json ... ```)
    text = content.strip()
    if text.startswith("```"):
        newline_idx = text.find("\n")
        if newline_idx != -1:
            text = text[newline_idx + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Parse JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract the best complete JSON object from the text
        data = _extract_json_object(text)
        if data is None:
            return

    if not isinstance(data, dict):
        return

    # Yield status
    status = data.get("status")
    if status:
        yield {"type": "status", "value": status}

    # Yield all actions from the array
    actions_list = data.get("actions", [])
    if isinstance(actions_list, list):
        for action in actions_list:
            if isinstance(action, dict):
                yield {"type": "action", "value": action}


def _iter_json_objects(text: str):
    """Yield every complete top-level JSON object found in text (brace counting)."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        end = -1
        for i in range(start, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == "\\" and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            break
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            pass
        start = text.find("{", end + 1)


def _extract_json_object(text: str) -> dict | None:
    """Extract the most relevant JSON state object from text.

    Prefers objects containing the agent protocol keys ('status'/'actions');
    falls back to the first complete object found.
    """
    first = None
    for obj in _iter_json_objects(text):
        if "status" in obj or "actions" in obj:
            return obj
        if first is None:
            first = obj
    return first
