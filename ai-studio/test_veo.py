import os
import requests
import time
import base64
from dotenv import load_dotenv

load_dotenv("backend/.env")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def run_veo_test():
    if not GOOGLE_API_KEY:
        print("❌ CRITICAL ERROR: GOOGLE_API_KEY missing in backend/.env")
        return

    print("🚀 Initiating Google DeepMind Veo Generation Matrix...")
    
    # 1. Create a tiny 1280x704 blue pixel base64 image (standard dimension)
    from PIL import Image
    import io
    img = Image.new('RGB', (1280, 704), color=(0, 200, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

    headers = {
        "Content-Type": "application/json"
    }

    # 2. Veo expects the generic Vertex/GenerativeLanguage long running prompt
    url = f"https://generativelanguage.googleapis.com/v1beta/models/veo-2.0-generate-001:predictLongRunning?key={GOOGLE_API_KEY}"
    payload = {
        "instances": [
            {
                "prompt": "Cinematic test of a futuristic car drifting.",
                "image": {
                    "bytesBase64Encoded": b64_img
                }
            }
        ],
        "parameters": {
            "aspectRatio": "16:9",
            "personGeneration": "ALLOW_ADULT"
        }
    }

    # Step 1: Submit the heavy rendering job
    print(f"📡 Requesting Veo Pipeline Architecture...")
    submit_resp = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if submit_resp.status_code != 200 and submit_resp.status_code != 202:
        print(f"❌ [AUTHORIZATION OR SERVER FAILURE]\nCode: {submit_resp.status_code}\nResponse: {submit_resp.text}")
        return
        
    print(f"✅ DeepMind Submission Accepted! Status Code: {submit_resp.status_code}")
    
    # Extract the Operation Target Node (This is Google's Asynchronous Polling URI System)
    op_name = submit_resp.json().get("name")
    if not op_name:
        print("❌ Google did not return an Operation ID. Render Failed.")
        print(f"Response received: {submit_resp.json()}")
        return
        
    print(f"⏳ Google Cluster assigned Operation ID: {op_name}. Beginning status polling...")
    
    # Step 2: Poll standard Google Generative Language Endpoint
    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={GOOGLE_API_KEY}"
    
    for _ in range(30):
        time.sleep(10)
        status_resp = requests.get(poll_url, headers=headers)
        status_data = status_resp.json()
        
        # Google's API natively populates the "done": True flag upon render finish
        is_done = status_data.get("done", False)
        
        if not is_done:
            print(f" > DeepMind Pipeline Status: [Generating Kinematics...]")
            continue
            
        print(f" > DeepMind Pipeline Status: [Job Node Complete]")
        if status_data.get("error"):
            print(f"❌ Google Server Rejected Job: {status_data['error']}")
            return
            
        print("🎬 GOOGLE VEO SUCCESSFULLY GENERATED THE VIDEO!")
        print(f"Payload Preview: {str(status_data)[:150]}...")
        return
            
    print("❌ Timeout: Video takes more than 5 minutes to render.")

if __name__ == "__main__":
    run_veo_test()
