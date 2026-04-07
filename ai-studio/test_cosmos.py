import os
import requests
import base64
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

load_dotenv("backend/.env")

NVIDIA_NIM_KEY = os.getenv("NVIDIA_NIM_KEY")
NVIDIA_COSMOS_URL = "https://ai.api.nvidia.com/v1/genai/nvidia/cosmos-1.0-diffusion-7b"

def test_cosmos_handshake():
    if not NVIDIA_NIM_KEY:
        print("❌ NVIDIA_NIM_KEY missing in .env")
        return

    # Create a simple 1280x704 JPEG for Cosmos
    img = Image.new('RGB', (1280, 704), color = (73, 109, 137))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    test_image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    data_uri = f"data:image/jpeg;base64,{test_image_b64}"

    headers = {
        "Authorization": f"Bearer {NVIDIA_NIM_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    payload = {
        "image": data_uri,
        "prompt": "Test animation: slow zoom into the center.",
        "negative_prompt": "blurry, low quality",
        "video_params": {
            "height": 704,
            "width": 1280,
            "frames_count": 24, 
            "frames_per_sec": 24
        },
        "seed": 42
    }

    print(f"Testing URL: {NVIDIA_COSMOS_URL}")
    try:
        # Use a shorter timeout for the test to verify header/auth first
        response = requests.post(NVIDIA_COSMOS_URL, headers=headers, json=payload, timeout=60)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error Body: {response.text[:1000]}")
        else:
            print("✅ Success! NVIDIA Cosmos 1.0 accepted the request.")
            res_json = response.json()
            if "video" in res_json:
                print("📹 Video data received in response.")
            else:
                print(f"Response keys: {list(res_json.keys())}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_cosmos_handshake()
