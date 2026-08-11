import requests

from app.agent.config import Config


Config.load()
cookies = Config.get_cookies()
headers = Config.get_headers()

params = {
    'lte_cursor.pinned': 'false',
}

response = requests.get(
    'https://chat.deepseek.com/api/v0/chat_session/fetch_page',
    params=params,
    cookies=cookies,
    headers=headers,
)


chats=response.json()['data']['biz_data']['chat_sessions']

for chat in chats:
    if chat['id']!="3a226cdb-86b9-41be-8564-db37a46ce293":
        
        json_data = {
            'chat_session_id': chat['id'],
        }

        response = requests.post('https://chat.deepseek.com/api/v0/chat_session/delete'
                                , cookies=cookies, headers=headers, json=json_data)

