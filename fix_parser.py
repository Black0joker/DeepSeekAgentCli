"""Script to replace the full_parse_sse function in app/agent/module.py"""

FILE_PATH = 'app/agent/module.py'

# Read the file
with open(FILE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start of full_parse_sse (module-level, no indentation)
start_marker = 'def full_parse_sse(response) -> Generator[Dict[str, Any], None, None]:'
start_idx = content.find(start_marker)
if start_idx == -1:
    print('ERROR: Could not find full_parse_sse function definition')
    exit(1)

print(f'Found full_parse_sse at character {start_idx}')

# Find the end: next module-level def after full_parse_sse
end_marker = 'def load_system_prompt'
end_idx = content.find(end_marker, start_idx)
if end_idx == -1:
    print('ERROR: Could not find end marker (load_system_prompt)')
    exit(1)

print(f'Found end marker at character {end_idx}')

# The new function
new_function = '''def full_parse_sse(response) -> Generator[Dict[str, Any], None, None]:
    """
    Parse SSE stream from DeepSeek API response.
    Accumulates the full RESPONSE content, then parses it as JSON.

    Supports both protocols:
    - normal: conversation_mode exists in initial response
    - thinking: no conversation_mode

    Yields:
    - {"type": "message_id", "value": int}
    - {"type": "status", "value": str}
    - {"type": "action", "value": dict}
    """
    message_sent = False
    protocol = None          # "normal" | "thinking"
    collecting = False
    content = ""

    for line in response.iter_lines(decode_unicode=True):
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
        else:
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
        newline_idx = text.find("\\n")
        if newline_idx != -1:
            text = text[newline_idx + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Parse JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract the first complete JSON object
        start = text.find("{")
        if start == -1:
            return
        depth = 0
        in_str = False
        esc = False
        end = -1
        for i in range(start, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == "\\\\" and in_str:
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
            return
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
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


'''

# Replace the old function with the new one
new_content = content[:start_idx] + new_function + content[end_idx:]

# Write the file back
with open(FILE_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('SUCCESS: full_parse_sse has been replaced.')
print(f'File size: {len(content)} -> {len(new_content)} chars')
