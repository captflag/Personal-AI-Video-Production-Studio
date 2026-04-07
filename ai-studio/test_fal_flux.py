import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")

FAL_FLUX_URL = "https://fal.run/fal-ai/flux/schnell"

async def test_fal_flux():
    api_key = os.getenv("FAL_KEY")
    if not api_key:
        print("❌ FAL_KEY missing in .env")
        return

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "prompt": "Cinematic film still, wide shot, futuristic city at night with neon lights, 8k, highly detailed",
        "image_size": {
            "width": 1280,
            "height": 720
        },
        "num_inference_steps": 4
    }
    
    print(f"📡 Testing fal.ai Flux 1 [schnell]...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(FAL_FLUX_URL, headers=headers, json=payload, timeout=60)
            print(f"📊 Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                image_url = result.get("images", [{}])[0].get("url")
                print(f"✅ Success! Image URL: {image_url}")
            else:
                print(f"❌ Error: {response.text}")
        except Exception as e:
            print(f"💥 Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_fal_flux())
