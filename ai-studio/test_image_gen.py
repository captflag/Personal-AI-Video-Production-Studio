import os
import requests
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

def test_nvidia_nim_sdxl():
    api_key = os.getenv("NVIDIA_NIM_KEY")
    if not api_key:
        print("❌ NVIDIA_NIM_KEY missing")
        return
    
    api_url = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    payload = {
        "text_prompts": [{"text": "A cinematic shot of a futuristic city", "weight": 1}],
        "steps": 30
    }
    
    print(f"📡 Testing NVIDIA NIM SDXL: {api_url}")
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        print(f"📊 Status: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Error: {response.text[:500]}")
    except Exception as e:
        print(f"💥 Exception: {e}")

def test_hf_flux():
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        print("❌ HUGGINGFACE_API_KEY missing")
        return
    
    api_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": "A cinematic shot of a futuristic city"}
    
    print(f"📡 Testing HF Flux: {api_url}")
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        print(f"📊 Status: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Error: {response.text[:500]}")
    except Exception as e:
        print(f"💥 Exception: {e}")

if __name__ == "__main__":
    test_nvidia_nim_sdxl()
    print("-" * 30)
    test_hf_flux()
