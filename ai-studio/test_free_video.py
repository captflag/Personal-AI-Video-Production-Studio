import asyncio
import os
from backend.agents.video_alchemist import query_hf_gradio, generate_static_fallback
from dotenv import load_dotenv

load_dotenv("backend/.env")

TEST_IMAGE_URL = "https://images.unsplash.com/photo-1506744038136-46273834b3fb?q=80&w=1000&auto=format&fit=crop"

async def test_fallbacks():
    print("🎬 Testing Advanced Cinematic Video Engine...")
    
    # 1. Test Advanced Cinematic Local Fallback
    prompts = [
        "Cinematic aerial shot, zoom in slowly, mountains",
        "Fast action sequence, zoom out, explosions",
        "Still landscape, slow pan left, forest"
    ]
    
    print("\n--- Testing Advanced Cinematic Local Engine ---")
    for i, p in enumerate(prompts):
        try:
            print(f"Rendering: '{p}'...")
            video_bytes = await generate_static_fallback(TEST_IMAGE_URL, p)
            fname = f"test_cinematic_{i}.mp4"
            with open(fname, "wb") as f:
                f.write(video_bytes)
            print(f"✅ Success! Saved to {fname}")
        except Exception as e:
            print(f"❌ Failed for '{p}': {e}")

    # 2. Test HF Gradio (Community API)
    print("\n--- Testing Hugging Face Gradio ---")
    try:
        p = "Cinematic sunrise over mountains, fluid motion"
        print(f"Requesting HF Space for: '{p}'...")
        video_bytes = await query_hf_gradio(TEST_IMAGE_URL, p)
        with open("test_gradio_hf.mp4", "wb") as f:
            f.write(video_bytes)
        print("✅ HF Gradio Success! Saved to test_gradio_hf.mp4")
    except Exception as e:
        print(f"⚠️ HF Gradio Failed: {e} (This is common if Space is busy)")

if __name__ == "__main__":
    asyncio.run(test_fallbacks())
