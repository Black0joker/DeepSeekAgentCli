"""
Test script for the SSE parser.
Reads logs/completion.log and feeds the SSE lines through the parser.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent.sse_parser import parse_sse


def read_sse_lines_from_log(log_path: str) -> list[str]:
    """Extract raw SSE lines from the completion log file.
    The log contains raw SSE data lines (starting with 'data: ' or 'event: ').
    """
    lines = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            raw_line = raw_line.rstrip('\n')
            # The log file contains raw SSE lines
            if raw_line.startswith('data: ') or raw_line.startswith('event: '):
                lines.append(raw_line)
            # Empty lines are SSE separators - include them too
            elif raw_line == '':
                lines.append('')
    return lines


def main():
    log_path = os.path.join('logs', 'completion.log')
    if not os.path.exists(log_path):
        print(f'ERROR: {log_path} not found')
        sys.exit(1)

    print(f'Reading SSE lines from: {log_path}')
    lines = read_sse_lines_from_log(log_path)
    print(f'Total lines: {len(lines)}')
    print(f'Data lines: {sum(1 for l in lines if l.startswith("data: "))}')
    print()

    # Feed lines through the parser
    print('--- Parser Output ---')
    events = list(parse_sse(lines))

    for event in events:
        if event['type'] == 'message_id':
            print(f'[MESSAGE_ID] {event["value"]}')
        elif event['type'] == 'status':
            print(f'[STATUS] {event["value"]}')
        elif event['type'] == 'action':
            action = event['value']
            print(f'[ACTION] id={action.get("id")} tool={action.get("tool")} args={action.get("arguments")}')

    print()
    print(f'Total events yielded: {len(events)}')

    # Validate expected results
    message_ids = [e for e in events if e['type'] == 'message_id']
    statuses = [e for e in events if e['type'] == 'status']
    actions = [e for e in events if e['type'] == 'action']

    print()
    print('--- Validation ---')
    passed = True

    # Check message_id
    if len(message_ids) == 1 and message_ids[0]['value'] == 4:
        print('PASS: message_id = 4')
    else:
        print(f'FAIL: message_id expected 4, got {message_ids}')
        passed = False

    # Check status
    if len(statuses) == 1 and statuses[0]['value'] == 'running':
        print('PASS: status = running')
    else:
        print(f'FAIL: status expected "running", got {statuses}')
        passed = False

    # Check actions - should have 2 actions
    if len(actions) == 2:
        print(f'PASS: {len(actions)} actions found')
    else:
        print(f'FAIL: expected 2 actions, got {len(actions)}')
        passed = False

    # Check first action
    if len(actions) >= 1:
        a1 = actions[0]['value']
        if a1.get('id') == '2' and a1.get('tool') == 'current_path' and a1.get('arguments') == {}:
            print('PASS: action 1 = current_path with empty args')
        else:
            print(f'FAIL: action 1 unexpected: {a1}')
            passed = False

    # Check second action
    if len(actions) >= 2:
        a2 = actions[1]['value']
        if a2.get('id') == '3' and a2.get('tool') == 'glob':
            pattern = a2.get('arguments', {}).get('pattern', '')
            if pattern == '**/*README*':
                print('PASS: action 2 = glob with pattern **/*README*')
            else:
                print(f'FAIL: action 2 pattern unexpected: {pattern}')
                passed = False
        else:
            print(f'FAIL: action 2 unexpected: {a2}')
            passed = False

    print()
    if passed:
        print('ALL TESTS PASSED')
    else:
        print('SOME TESTS FAILED')
        sys.exit(1)


if __name__ == '__main__':
    main()
