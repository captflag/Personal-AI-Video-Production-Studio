import os
import httpx
import asyncio
from dotenv import load_dotenv

# Load credentials from backend/.env
load_dotenv("backend/.env")

FAL_KEY = os.getenv("FAL_KEY")
FAL_KLING_URL = "https://fal.run/fal-ai/kling-video/v3/standard/image-to-video"

# A public sample image for testing (a cinematic landscape)
TEST_IMAGE_URL = "https://images.unsplash.com/photo-1506744038136-46273834b3fb?q=80&w=1000&auto=format&fit=crop"

async def test_kling_handshake():
    print("🚀 Starting fal.ai Kling 3.0 Handshake Test...")
    
    if not FAL_KEY:
        print("❌ Error: FAL_KEY not found in backend/.env")
        return

    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "prompt": "Cinematic aerial shot of a foggy mountain range at sunrise, realistic motion.",
        "image_url": TEST_IMAGE_URL,
        "duration": "5",
        "aspect_ratio": "16:9",
    }

    print(f"📡 Sending request to {FAL_KLING_URL}...")
    
    async with httpx.AsyncClient() as client:
        try:
            # We use a high timeout because video generation is a heavy process
            response = await client.post(FAL_KLING_URL, headers=headers, json=payload, timeout=300)
            
            print(f"📊 Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                video_url = result.get("video", {}).get("url")
                if video_url:
                    print(f"✅ Success! Video generated at: {video_url}")
                else:
                    print(f"⚠️ Response received but video URL missing. Keys: {list(result.keys())}")
            else:
                print(f"❌ API Error: {response.status_code}")
                print(f"Details: {response.text[:500]}")
                
        except Exception as e:
            print(f"💥 Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_kling_handshake())
