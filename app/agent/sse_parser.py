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
"""
import json
import re
from typing import Any, Dict, Generator, Iterable


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

    for line in lines:
        if not line or not line.startswith("data: "):
            continue

        try:
            obj = json.loads(line[6:])
        except json.JSONDecodeError:
            continue

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
            # Normal protocol may already contain a RESPONSE fragment.
            if protocol == "normal":
                fragments = response_obj.get("fragments", [])
                if fragments:
                    last = fragments[-1]
                    if last.get("type") == "RESPONSE":
                        collecting = True
                        content = last.get("content", "")
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
                if fragments and fragments[0].get("type") == "RESPONSE":
                    collecting = True
                    content = fragments[0].get("content", "")
            elif collecting:
                path = obj.get("p")
                if path == "response/fragments/-1/content":
                    content += obj.get("v", "")
                elif path is None and isinstance(obj.get("v"), str):
                    content += obj["v"]
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
        # Fallback: extract the first complete JSON object
        data = _extract_json_object(text)
        if data is None:
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


def _extract_json_object(text: str) -> dict | None:
    """Extract the first complete JSON object from text using brace counting."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
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
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
