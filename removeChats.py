"""Utility to bulk-delete DeepSeek chat sessions.

Usage:
    python removeChats.py [KEEP_CHAT_ID]

If KEEP_CHAT_ID is provided, that session is preserved.
Otherwise, ALL sessions are deleted.

Sessions are fetched through DeepSeekClient.fetch_chats(), which follows
pagination, so all sessions (not just the first page) are processed.
"""
import sys
import requests

from app.agent.config import Config
from app.agent.module import create_client


def main():
    # Determine which chat to keep (optional CLI argument)
    keep_id = sys.argv[1] if len(sys.argv) > 1 else None

    Config.load()
    cookies = Config.get_cookies()
    headers = Config.get_headers()
    client = create_client()

    chats = client.fetch_chats()
    deleted = 0
    skipped = 0

    for chat in chats:
        chat_id = chat['id']
        title = chat.get('title', 'Untitled')

        if keep_id and chat_id == keep_id:
            print(f"  [SKIP] {title} ({chat_id})")
            skipped += 1
            continue

        json_data = {
            'chat_session_id': chat_id,
        }

        del_response = requests.post(
            'https://chat.deepseek.com/api/v0/chat_session/delete',
            cookies=cookies,
            headers=headers,
            json=json_data,
        )

        if del_response.status_code == 200:
            print(f"  [DEL]  {title} ({chat_id})")
            deleted += 1
        else:
            print(f"  [ERR]  {title} ({chat_id}) - status {del_response.status_code}")

    print(f"\nDone. Deleted: {deleted}, Skipped: {skipped}, Total: {len(chats)}")


if __name__ == '__main__':
    main()
