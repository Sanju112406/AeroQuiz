import requests, os
from dotenv import load_dotenv
load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")
r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
updates = r.json().get("result", [])
if not updates:
    print("No updates found. Make sure you sent a message in the group first.")
for u in updates:
    chat = u.get("message", {}).get("chat", {})
    if chat:
        print(f"Chat ID: {chat.get('id')}  |  Type: {chat.get('type')}  |  Name: {chat.get('title', chat.get('first_name', '?'))}")
