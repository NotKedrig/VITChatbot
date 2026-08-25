import requests
import time
import json
from datetime import datetime, timezone
from dateutil.tz import gettz

API_URL = "http://127.0.0.1:8000/api/chat"

def test_query(text: str):
    print(f"\n--- Testing: '{text}' ---")
    current_utc = datetime.now(timezone.utc)
    current_ist = current_utc.astimezone(gettz("Asia/Kolkata"))
    print(f"Current UTC: {current_utc}")
    print(f"Current IST: {current_ist}")
    
    payload = {
        "messages": [{"role": "user", "content": text}],
        "thread_id": "test_thread",
        "student_id": "manual_test_user",
        "message": text
    }
    try:
        response = requests.post(API_URL, json=payload, timeout=25)
        if response.status_code == 200:
            data = response.json()
            reply = data.get("messages", [{}])[-1].get("content")
            print(f"Reply: {reply}")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_query("Remind me to study DB in 5 mins")
    time.sleep(2)
    test_query("Remind me to study DSA tomorrow at 7 PM")
