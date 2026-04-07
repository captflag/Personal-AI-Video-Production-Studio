import os
import requests
from dotenv import load_dotenv

load_dotenv("backend/.env")

def test_nvidia_nim_sdxl():
    api_key = os.getenv("NVIDIA_NIM_KEY")
    if not api_key:
        return "❌ NVIDIA_NIM_KEY missing"
    
    api_url = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    payload = {
        "text_prompts": [{"text": "A cinematic shot of a futuristic city", "weight": 1}],
        "steps": 30
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"✅ NVIDIA SDXL: OK (200)"
        else:
            return f"❌ NVIDIA SDXL: {response.status_code} - {response.text[:200]}"
    except Exception as e:
        return f"💥 NVIDIA SDXL Exception: {e}"

def test_hf_flux():
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        return "❌ HUGGINGFACE_API_KEY missing"
    
    api_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": "A cinematic shot of a futuristic city"}
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"✅ HF Flux: OK (200)"
        else:
            return f"❌ HF Flux: {response.status_code} - {response.text[:200]}"
    except Exception as e:
        return f"💥 HF Flux Exception: {e}"

if __name__ == "__main__":
    results = []
    results.append(test_nvidia_nim_sdxl())
    results.append(test_hf_flux())
    
    with open("test_results_image.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
