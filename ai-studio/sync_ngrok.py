import requests
import os
import time
from dotenv import load_dotenv

def get_ngrok_url():
    for i in range(10):
        print(f"Attempt {i+1}: Checking ngrok API...")
        try:
            res = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
            res.raise_for_status()
            tunnels = res.json()["tunnels"]
            for t in tunnels:
                if t["proto"] == "https":
                    return t["public_url"]
        except:
            pass
        time.sleep(2)
    return None

def update_env(new_url):
    env_path = "backend/.env"
    with open(env_path, "r") as f:
        lines = f.readlines()
    with open(env_path, "w") as f:
        for line in lines:
            if line.startswith("N8N_WEBHOOK_URL="):
                f.write(f'N8N_WEBHOOK_URL="{new_url}/webhook/ai-studio-hitl"\n')
            else:
                f.write(line)
    print(f"Set .env to: {new_url}")

url = get_ngrok_url()
if url:
    update_env(url)
else:
    print("Ngrok not found.")
