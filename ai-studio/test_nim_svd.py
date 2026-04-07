import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv("backend/.env")

NVIDIA_NIM_KEY = os.getenv("NVIDIA_NIM_KEY")
NIM_SVD_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-video-diffusion"

def test_nim_svd():
    if not NVIDIA_NIM_KEY:
        print("❌ NVIDIA_NIM_KEY missing in .env")
        return

    # Use a tiny transparent 1x1 pixel base64 for testing payload speed
    # Actual SVD needs a real image, lets use a small placeholder
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    data_uri = f"data:image/png;base64,{test_image_b64}"

    headers = {
        "Authorization": f"Bearer {NVIDIA_NIM_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    payload = {
        "image": data_uri,
        "seed": 0,
        "cfg_scale": 3.0,
        "motion_bucket_id": 127,
    }

    print(f"Testing URL: {NIM_SVD_URL}")
    try:
        response = requests.post(NIM_SVD_URL, headers=headers, json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error Body: {response.text}")
        else:
            print("✅ Success! (at least header accepted)")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_nim_svd()
