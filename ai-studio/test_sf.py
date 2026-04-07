import requests

API_KEY = "sk-ofnrmnjpflxgecucpafaqyqydfwiplxncaeushxioyslosqg"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def run_diagnostic():
    print("Diagnostics Starting for SiliconFlow API...")
    
    # 1. Test Root Authentication
    print("\n--- Test 1/2: Global Account Authentication ---")
    auth_resp = requests.get("https://api.siliconflow.cn/v1/user/info", headers=HEADERS)
    print(f"Status Code: {auth_resp.status_code}")
    print(f"Response: {auth_resp.text}")
    
    if auth_resp.status_code == 401:
        print("\n[CRITICAL FAILURE]: The API Key itself is completely invalid or revoked. SiliconFlow servers do not recognize you.")
        return

    # 2. Test Video Model Access (Free Tier Checking)
    print("\n--- Test 2/2: Image-To-Video Model Authorizations ---")
    payload = {
        "model": "Lightricks/LTX-Video",
        "prompt": "Test video generation",
        "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    }
    vid_resp = requests.post("https://api.siliconflow.cn/v1/video/submit", headers=HEADERS, json=payload)
    print(f"Status Code: {vid_resp.status_code}")
    print(f"Response: {vid_resp.text}")
    
    if vid_resp.status_code == 402 or "Insufficient Balance" in vid_resp.text or "unauthorized" in vid_resp.text.lower():
        print("\n[PAYWALL DETECTED]: Your account is fully verified, but SiliconFlow strictly prohibits using free/trial credits on Video Models! You MUST top up your wallet with $1 to unlock video endpoints.")

if __name__ == "__main__":
    run_diagnostic()
