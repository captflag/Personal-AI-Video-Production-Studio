import os
import requests
import time
import base64
from dotenv import load_dotenv

load_dotenv("backend/.env")

# Must use the new Async cloud architecture for Cosmos, not the synchronous /genai endpoint
API_KEY = "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"
COSMOS_URL = "https://ai.api.nvidia.com/v1/cosmos/nvidia/cosmos-1.0-7b-diffusion-video2world"

def run_cosmos_test():
    if not API_KEY:
        print("❌ CRITICAL ERROR: NVIDIA_NIM_KEY missing in backend/.env")
        return

    print("🚀 Firing sequence initiated for NVIDIA Cosmos 7B Video2World...")
    
    # 1. Create a tiny 1280x704 blue pixel base64 image (the exact required resolution)
    from PIL import Image
    import io
    img = Image.new('RGB', (1280, 704), color=(0, 100, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64_img = base64.b64encode(buf.getvalue()).decode("ascii")
    data_uri = f"data:image/jpeg;base64,{b64_img}"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "image": data_uri,
        "prompt": "Test video, dramatic camera pan.",
        "negative_prompt": "static, blurry, poor quality",
    }

    # Step 1: Submit the heavy rendering job
    print(f"📡 Requesting Cosmos rendering via: {COSMOS_URL}")
    submit_resp = requests.post(COSMOS_URL, headers=headers, json=payload, timeout=30)
    
    if submit_resp.status_code != 202 and submit_resp.status_code != 200:
        print(f"❌ [AUTHORIZATION OR SEREVER FAILURE]\nCode: {submit_resp.status_code}\nResponse: {submit_resp.text}")
        return
        
    print(f"✅ Submission Accepted! Status Code: {submit_resp.status_code}")
    print("Response payload:", submit_resp.json())
        
    # NVIDIA Cosmos requires Asynchronous Polling. We must extract the NVCF-REQID from headers
    req_id = submit_resp.headers.get("NVCF-REQID")
    if not req_id:
        print("❌ NVIDIA did not return a NVCF-REQID header. Cannot poll for the video.")
        print(f"Headers received: {submit_resp.headers}")
        return
        
    print(f"⏳ NVIDIA Cluster assigned Request ID: {req_id}. Beginning status polling...")
    
    # Step 2: Poll standard NVIDIA Cloud Function Status Endpoint
    poll_url = f"https://api.nvcf.nvidia.com/v2/nvcf/pexec/status/{req_id}"
    
    for _ in range(30):
        time.sleep(10)
        status_resp = requests.get(poll_url, headers=headers)
        status_data = status_resp.json()
        status_code = status_data.get("status")
        
        print(f" > Pipeline Status: [{status_code}]")
        
        if status_code == "fulfilled" or status_code == "finished":
            print("🎬 NVIDIA COSMOS SUCCESSFULLY GENERATED THE VIDEO!")
            return
        elif status_code == "failed" or status_code == "rejected":
            print(f"❌ NVIDIA Server Rejected Job: {status_data}")
            return
            
    print("❌ Timeout: Video takes more than 5 minutes to render.")

if __name__ == "__main__":
    run_cosmos_test()
