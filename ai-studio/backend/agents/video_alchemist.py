import os
import requests
import httpx
from io import BytesIO
import tempfile
import numpy as np
import random
from backend.utils_auth import get_supabase_client
from backend.utils_sync import sync_pipeline_state
import asyncio
import structlog
import base64
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.state import UniversalGraphState
from moviepy.editor import ImageClip, vfx, CompositeVideoClip, ColorClip, VideoFileClip
from gradio_client import Client, handle_file

logger = structlog.get_logger()

# URLs & Constants
FAL_KLING_URL = "https://fal.run/fal-ai/kling-video/v3/standard/image-to-video"
HF_SPACE_ID = "THUDM/CogVideoX-5B-demo"

# --- Advanced Cinematic Helpers ---

def cubic_ease_in_out(t: float) -> float:
    """Standard cubic easing for smooth starts and stops."""
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - ((-2 * t + 2) ** 3) / 2

def apply_cinematic_filters(frame: np.ndarray) -> np.ndarray:
    """Applies film grain, vignette, and contrast adjustments."""
    h, w, c = frame.shape
    
    # 1. Subtle Contrast Boost (using NumPy)
    frame = frame.astype(np.float32) / 255.0
    frame = (frame - 0.5) * 1.1 + 0.5
    
    # 2. Dynamic Film Grain
    noise = np.random.normal(0, 0.02, (h, w, c))
    frame = np.clip(frame + noise, 0, 1)
    
    # 3. Vignette
    y = np.linspace(-1, 1, h)
    x = np.linspace(-1, 1, w)
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X**2 + Y**2)
    vignette = np.clip(1.2 - radius * 0.5, 0, 1)
    for i in range(3):
        frame[:, :, i] *= vignette
        
    return (np.clip(frame, 0, 1) * 255).astype(np.uint8)

def analyze_motion_direction(prompt: str):
    """Parses prompt to decide zoom direction and speed."""
    p = prompt.lower()
    params = {"zoom": "in", "pan": "none", "speed": 1.0}
    
    if "zoom out" in p or "wide" in p: params["zoom"] = "out"
    if "pan left" in p: params["pan"] = "left"
    if "pan right" in p: params["pan"] = "right"
    if "fast" in p or "explosive" in p: params["speed"] = 1.8
    if "slow" in p or "still" in p: params["speed"] = 0.6
    
    return params

# --- Agent Tasks ---

async def query_google_veo(image_url: str, prompt: str, api_key: str) -> bytes:
    """Highly accurate Google DeepMind Veo 2.0 Image-to-Video Engine"""
    logger.info("google_veo_query_started")
    async with httpx.AsyncClient() as client:
        # Download and encode the base image
        img_resp = await client.get(image_url, timeout=30)
        img_resp.raise_for_status()
        b64_img = base64.b64encode(img_resp.content).decode("ascii")

        # Initiate Veo Async Job via standard Gemini REST endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/veo-2.0-generate-001:predictLongRunning?key={api_key}"
        payload = {
            "instances": [
                {
                    "prompt": prompt,
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
        
        # Initiate the long-running generation
        submit_resp = await client.post(url, json=payload, timeout=60)
        submit_resp.raise_for_status()
        op_name = submit_resp.json().get("name")
        
        if not op_name:
            raise ValueError(f"Veo failed to return operation name: {submit_resp.json()}")
            
        logger.info("veo_job_initiated", operation=op_name)
        
        # Asynchronous Polling Loop for Google Cloud Functions
        poll_url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={api_key}"
        for _ in range(60): # Max 10 minutes wait
            await asyncio.sleep(10)
            poll_resp = await client.get(poll_url, timeout=30)
            poll_resp.raise_for_status()
            status = poll_resp.json()
            
            if status.get("done"):
                if status.get("error"):
                    raise ValueError(f"Veo failed during render: {status['error']}")
                    
                resp_data = status.get("response", {})
                vid_data = resp_data.get("generatedVideo", {}).get("bytesBase64Encoded")
                if vid_data: return base64.b64decode(vid_data)
                
                vid_uri = resp_data.get("generatedVideo", {}).get("uri")
                if vid_uri:
                    vid_dl = await client.get(vid_uri, timeout=120)
                    return vid_dl.content
                    
                raise ValueError(f"Unknown Veo success payload: {status}")
                
        raise TimeoutError("Veo generation timed out after 10 minutes.")

async def query_fal_kling(image_url: str, motion_prompt: str) -> bytes:
    """Calls fal.ai Kling 3.0 Standard with Structural Texture Locking."""
    api_key = os.getenv("FAL_KEY")
    if not api_key: raise ValueError("FAL_KEY missing")
    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    
    # NEW: Temporal Consistency & Preservation Tokens
    locked_prompt = f"{motion_prompt}, high temporal consistency, locked textures, zero flickering, stable cinematography, RIGID JOINT STRUCTURES, ZERO ANATOMICAL MORPHING"
    # Negative prompt for zero-compromise stability
    negative_prompt = "joint melting, background warping, pixel stretching, texture shimmering, flickering, morphed limbs, character eating background"
    
    payload = {
        "prompt": locked_prompt, 
        "negative_prompt": negative_prompt, # Explicitly guarding against melting/warping
        "image_url": image_url, 
        "duration": "5", 
        "aspect_ratio": "16:9",
        "relevance_to_image": 0.98 # MAX LOCK: Treats keyframe as a structural master
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(FAL_KLING_URL, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        res = response.json(); url = res.get("video", {}).get("url")
        if not url: raise KeyError("No video URL")
        return (await client.get(url, timeout=120)).content

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
async def query_hf_gradio(image_url: str, prompt: str) -> bytes:
    """Calls Hugging Face Space via Gradio using VIP token prioritized queueing."""
    logger.info("hf_gradio_query_started", space=HF_SPACE_ID)
    def call_gradio():
        # Passing your HF Token instantly bumps your job to priority in the Space Queue
        hf_token = os.getenv("HUGGINGFACE_API_KEY") 
        client = Client(HF_SPACE_ID, hf_token=hf_token) if hf_token else Client(HF_SPACE_ID)
        
        result = client.predict(prompt=prompt, image=handle_file(image_url), api_name="/predict")
        if isinstance(result, tuple): result = result[0]
        
        with open(result, "rb") as f: return f.read()
    return await asyncio.to_thread(call_gradio)

async def query_nvidia_svd(image_url: str, prompt: str, api_key: str, state: UniversalGraphState) -> bytes:
    """Robust fallback: Uploads Base64 Image natively to NVIDIA Stable Video Diffusion (SVD)"""
    logger.info("nvidia_svd_query_started")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient() as client:
        # Download the image generated by Agent 4
        img_resp = await client.get(image_url, timeout=30)
        img_resp.raise_for_status()
        
        # SVD requires standard 1024x576 or 1024x1024. Resizing for temporal safety.
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        img = img.resize((1024, 576), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        test_image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        data_uri = f"data:image/jpeg;base64,{test_image_b64}"

        # NVIDIA SVD translates prompt energy into motion buckets
        # Scaled from Motion Director's 1-10 scores to hardware 1-255 buckets
        intensity = state.get("scenes", [{}])[0].get("motion_intensity", 5) 
        # Attempt to find the specific scene's intensity if possible
        for s in state.get("scenes", []):
            if s.get("keyframe_url") == image_url:
                intensity = s.get("motion_intensity", 5)
                break
        
        m_bucket = int((intensity / 10.0) * 255)

        payload = {
            "image": data_uri,
            "seed": random.randint(1, 999999),
            "cfg_scale": 3.0,
            "motion_bucket_id": m_bucket,
            "aug_level": 0.05 # Lower level locks the original keyframe structure tighter
        }

        # Send POST identically to NVIDIA REST engine
        res = await client.post("https://ai.api.nvidia.com/v1/genai/stabilityai/stable-video-diffusion", headers=headers, json=payload, timeout=300)
        res.raise_for_status()
        
        res_json = res.json()
        video_b64 = res_json.get("video")
        if not video_b64:
            raise ValueError(f"NVIDIA SVD failed to return a video block: {res_json}")
            
        return base64.b64decode(video_b64)

async def generate_static_fallback(image_url: str, prompt: str) -> bytes:
    """Advanced Cinematic Fallback: Iterative frame conditioning with temporal smoothing (Zero Flicker)."""
    logger.info("generating_advanced_cinematic_fallback", prompt=prompt)
    async with httpx.AsyncClient() as client:
        resp = await client.get(image_url); resp.raise_for_status()
        img_data = resp.content

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_in, \
         tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f_out:
        f_in.write(img_data); f_in.close(); f_out.close()
        
        import cv2
        base_img = cv2.imread(f_in.name)
        base_img = cv2.cvtColor(base_img, cv2.COLOR_BGR2RGB)
        
        # 1. Setup Motion
        m = analyze_motion_direction(prompt)
        duration = 4.0
        fps = 24
        total_frames = int(duration * fps)
        
        h, w, c = base_img.shape
        
        frames = []
        
        # Starting frame
        current_frame = base_img.astype(np.float32)
        
        # Pre-calculated static noise to prevent flickering
        static_noise = np.random.normal(0, 5.0, (h, w, c)).astype(np.float32)
        
        for i in range(total_frames):
            t = i / float(fps)
            eased_t = cubic_ease_in_out(t / duration)
            
            # Zoom Effect
            if m["zoom"] == "in": scale = 1.0 + (0.003 * m["speed"])
            else: scale = 1.0 - (0.003 * m["speed"])
            
            # Sub-pixel pan
            jitter_x = np.sin(t * 2.5) * 0.5
            jitter_y = np.cos(t * 2.1) * 0.3
            
            # Iterative warping: frame_i = warp(frame_{i-1})
            M = np.float32([[scale, 0, (1-scale)*w/2 + jitter_x], 
                            [0, scale, (1-scale)*h/2 + jitter_y]])
                            
            next_frame = cv2.warpAffine(current_frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            
            # Temporal Smoothing (EMA Blend) to guarantee zero flickering
            # frame 1 helps generate frame 2, smoothed!
            if i > 0:
                next_frame = cv2.addWeighted(next_frame, 0.85, current_frame, 0.15, 0)
                
            current_frame = next_frame
            
            # Apply static noise and vignette
            final_out = np.clip(current_frame + static_noise, 0, 255)
            
            frames.append(final_out.astype(np.uint8))
            
        from moviepy.editor import ImageSequenceClip
        clip = ImageSequenceClip(frames, fps=fps)
        clip.write_videofile(f_out.name, fps=fps, codec="libx264", audio=False, 
                                   logger=None, threads=4, preset="medium")
        
        with open(f_out.name, "rb") as f: video_bytes = f.read()
        os.unlink(f_in.name); os.unlink(f_out.name)
        return video_bytes

async def agent_video_alchemist(state: UniversalGraphState) -> UniversalGraphState:
    job_id = state["job_id"]; scenes = state.get("scenes", []); supabase = get_supabase_client()
    for scene in scenes:
        img_url = scene.get("keyframe_url")
        if not img_url or "FAILED" in img_url or "unsplash" in img_url: continue
        try:
            await sync_pipeline_state(job_id, state, "MOTION_GENERATION", 
                status_message=f"Cinematic rendering scene {scene.get('scene_number')}...")
            
            # [PRODUCTION CHECK] Only produce video if scene is explicitly approved
            if scene.get("status") != "APPROVED":
                logger.info("scene_skipped_unapproved", scene=scene.get('scene_number'))
                continue
            
            # [IDEMPOTENCY] Skip if video already exists
            if scene.get("motion_video_url") and "FAILED" not in scene.get("motion_video_url", ""):
                logger.info("motion_skipped_already_exists", scene=scene.get('scene_number'))
                continue

            subject_action = scene.get("subject_action", "Subject moves kinetically.")
            prompt_kling = f"{subject_action}. {scene.get('motion_prompt_kling') or scene.get('motion_prompt') or scene.get('script_text', 'Cinematic landscape')}"
            prompt_cogvideo = f"{subject_action}. {scene.get('motion_prompt_cogvideo') or scene.get('motion_prompt') or scene.get('script_text', 'Cinematic landscape')}"
            video_bytes = None; method_used = "NONE"

            # Try Providers natively with exclusive prompts
            google_key = os.getenv("GOOGLE_API_KEY")
            nvidia_key = os.getenv("NVIDIA_NIM_KEY")
            
            # 1. Google DeepMind Veo (Highest Physical Accuracy)
            if google_key:
                try: video_bytes = await query_google_veo(img_url, prompt_cogvideo, google_key); method_used = "GOOGLE_VEO"
                except Exception as e: logger.warning("google_veo_failed", error=str(e))
                
            # 2. NVIDIA SVD (Vigorous Camera Motion Base)
            if not video_bytes and nvidia_key:
                try: video_bytes = await query_nvidia_svd(img_url, prompt_cogvideo, nvidia_key, state); method_used = "NVIDIA_SVD"
                except Exception as e: logger.warning("nvidia_svd_failed", error=str(e))
                
            # 3. Fal Kling 3.0 Fallback
            if not video_bytes and os.getenv("FAL_KEY"):
                try: video_bytes = await query_fal_kling(img_url, prompt_kling); method_used = "KLING_3.0"
                except Exception as e: logger.warning("kling_failed", error=str(e))
                
            # 4. VIP Hugging Face Priority Access
            if not video_bytes:
                try: video_bytes = await query_hf_gradio(img_url, prompt_cogvideo); method_used = "HF_GRADIO"
                except Exception as e: logger.warning("hf_gradio_failed", error=str(e))
                
            # 5. Zero-GPU Local Machine Math Engine Fallback
            if not video_bytes:
                video_bytes = await generate_static_fallback(img_url, prompt_cogvideo); method_used = "CINEMATIC_ENGINE_LOCAL"

            filename = f"{job_id}_scene_{scene.get('scene_number')}.mp4"
            supabase.storage.from_("videos").upload(path=filename, file=video_bytes, 
                file_options={"content-type": "video/mp4", "x-upsert": "true"})
            scene["motion_video_url"] = supabase.storage.from_("videos").get_public_url(filename)
            scene["motion_method"] = method_used
            logger.info("rendering_complete", scene=scene.get('scene_number'), method=method_used)
        except Exception as e: logger.error("critical_render_fail", error=str(e), scene=scene.get('scene_number'))
    state["pipeline_stage"] = "MOTION_GENERATION"; state["current_agent"] = "vision_qa"
    return state
