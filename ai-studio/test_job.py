import requests
import json

url = "http://127.0.0.1:8000/jobs/start"
headers = {"X-API-Key": "dev-secret-key-123", "Content-Type": "application/json"}
data = {"raw_prompt": "Cinematic test from terminal", "chat_id": "terminal-test"}

try:
    r = requests.post(url, headers=headers, json=data)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.json()}")
except Exception as e:
    print(f"Error: {e}")
