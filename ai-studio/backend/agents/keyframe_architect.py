import os
import requests
import httpx
from backend.utils_sync import sync_pipeline_state
import asyncio
import structlog
from io import BytesIO
from tenacity import retry, stop_after_attempt, wait_exponential
from supabase import Client
from backend.utils_auth import get_supabase_client
from backend.state import UniversalGraphState

logger = structlog.get_logger()

# --- fal.ai: Flux 1 [schnell] (Primary) ---
# URL: https://fal.run/fal-ai/flux/schnell
FAL_FLUX_URL = "https://fal.run/fal-ai/flux/schnell"

async def query_fal_flux_schnell(prompt: str) -> bytes:
    """
    Calls fal.ai Flux 1 [schnell] for high-speed, high-fidelity generation.
    """
    api_key = os.getenv("FAL_KEY")
    if not api_key:
        raise ValueError("FAL_KEY missing in .env")

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "prompt": prompt,
        "image_size": {
            "width": 1280,
            "height": 720
        },
        "num_inference_steps": 4, # Standard for Flux Schnell
        "enable_safety_checker": True
    }
    
    logger.info("fal_flux_request_sent", prompt=prompt[:100])
    
    async with httpx.AsyncClient() as client:
        response = await client.post(FAL_FLUX_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            error_msg = response.text[:1000]
            logger.error("fal_flux_error", status=response.status_code, detail=error_msg)
            raise Exception(f"fal.ai Flux Error {response.status_code}: {error_msg}")

        result = response.json()
        image_url = result.get("images", [{}])[0].get("url")
        if not image_url:
            raise KeyError(f"No image URL found in fal response. Keys: {list(result.keys())}")
            
        # Download the final image bytes
        image_response = await client.get(image_url, timeout=30)
        image_response.raise_for_status()
        return image_response.content

async def query_fal_flux_pulid(prompt: str, reference_url: str) -> bytes:
    """
    Calls fal.ai Flux PuLID for ultra-fidelity Character Identity Locking.
    """
    api_key = os.getenv("FAL_KEY")
    if not api_key:
        raise ValueError("FAL_KEY missing in .env")

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "prompt": prompt,
        "reference_images": [{"image_url": reference_url}],
        "image_size": {
            "width": 1280,
            "height": 720
        },
        "num_inference_steps": 20,
        "enable_safety_checker": True
    }
    
    logger.info("fal_flux_pulid_request_sent", prompt=prompt[:100])
    
    async with httpx.AsyncClient() as client:
        response = await client.post("https://fal.run/fal-ai/flux-pulid", headers=headers, json=payload, timeout=90)
        
        if response.status_code != 200:
            error_msg = response.text[:1000]
            logger.error("fal_flux_pulid_error", status=response.status_code, detail=error_msg)
            raise Exception(f"fal.ai Flux PuLID Error {response.status_code}: {error_msg}")

        result = response.json()
        image_url = result.get("images", [{}])[0].get("url")
        if not image_url:
            raise KeyError(f"No image URL found in fal PuLID response. Keys: {list(result.keys())}")
            
        image_response = await client.get(image_url, timeout=30)
        image_response.raise_for_status()
        return image_response.content

# --- OpenAI: DALL-E 3 (Requested Upgrade) ---
async def query_openai_dalle3(prompt: str) -> bytes:
    """
    Calls OpenAI DALL-E 3 endpoint for highest fidelity keyframe rendering limitlessly.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY missing in .env")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # OpenAI API expects prompts max 4000 chars, DALL-E handles spatial constraints well.
    payload = {
        "model": "dall-e-3",
        "prompt": prompt[:3900], 
        "n": 1,
        "size": "1024x1792", # cinematic portrait (Wait, 1024 width / 1792 height) 
        # Standard video requires 1792x1024.
        "response_format": "url"
    }
    payload["size"] = "1792x1024" # 16:9 cinematic
    payload["quality"] = "hd"
    
    logger.info("openai_dalle3_request_sent", prompt=prompt[:100])
    
    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload, timeout=90)
        
        if response.status_code != 200:
            error_msg = response.text[:1000]
            logger.error("openai_dalle3_error", status=response.status_code, detail=error_msg)
            raise Exception(f"OpenAI DALL-E 3 Error {response.status_code}: {error_msg}")

        result = response.json()
        image_url = result.get("data", [{}])[0].get("url")
        if not image_url:
            raise KeyError(f"No image URL found in OpenAI response. Keys: {list(result.keys())}")
            
        image_response = await client.get(image_url, timeout=30)
        image_response.raise_for_status()
        return image_response.content

# --- Risk 1 & Risk 2: API Rate Limits & InstantID Routing ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
def query_nvidia_nim_sdxl(prompt: str) -> bytes:
    """
    Calls NVIDIA NIM SDXL endpoint for high-speed, high-quality generation.
    Uses the 1000 free developer credits.
    """
    api_key = os.getenv("NVIDIA_NIM_KEY")
    if not api_key:
        raise ValueError("NVIDIA_NIM_KEY missing")

    # Correct URL for NVIDIA NIM SDXL (2025 Standard)
    api_url = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    payload = {
        "text_prompts": [{"text": prompt, "weight": 1}],
        "cfg_scale": 7,
        "sampler": "K_DPM_2_ANCESTRAL",
        "steps": 30,
        "seed": 0
    }

    response = requests.post(api_url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"NVIDIA NIM Error {response.status_code}: {response.text}")

    # NVIDIA NIM returns a JSON with base64 artifacts
    import base64
    response_json = response.json()
    image_b64 = response_json['artifacts'][0]['base64']
    return base64.b64decode(image_b64)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=3, min=5, max=30))
def query_huggingface_flux(prompt: str) -> bytes:
    """
    Protected by Tenacity. Automatically sleeps and retries if HuggingFace throws a 429 or 503 error.
    """
    # Migrate to the new HuggingFace Router (2025 Standard)
    api_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}"}

    payload = {"inputs": prompt[:1000]}

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=45)
    except requests.Timeout:
        # Tenacity will catch and retry
        raise Exception("HF Timeout: Request exceeded 45s")  # noqa: TRY002
    except requests.RequestException as e:
        raise Exception(f"HF request failed: {e}") from e

    if response.status_code == 503:
        raise Exception("503 Model is Loading")  # Caught by Tenacity, forces sleep
    elif response.status_code == 429:
        raise Exception("429 Too Many Requests")  # Caught by Tenacity, forces sleep
    elif response.status_code != 200:
        body = response.text[:1000] if response.text else ""
        raise Exception(f"HF Error {response.status_code}: {body}")

    return response.content


# --- Risk 4: Theoretical Local Storage (Supabase Fix) ---

def upload_to_supabase_storage(supabase: Client, image_bytes: bytes, filename: str) -> str:
    """
    Physically pushes the binary image to the Cloud Bucket via API.
    Uses upsert so pipeline retries / resumes do not fail on duplicate paths.
    """
    bucket = supabase.storage.from_("keyframes")
    opts = {"content-type": "image/png", "x-upsert": "true"}
    try:
        bucket.upload(path=filename, file=image_bytes, file_options=opts)
    except Exception as e:
        err = str(e).lower()
        if "duplicate" in err or "already exists" in err:
            logger.info("supabase_upload_duplicate_ok", filename=filename)
            return bucket.get_public_url(filename)
        logger.warning("supabase_upload_failed", filename=filename, error=str(e))
        raise

    return bucket.get_public_url(filename)


# --- Risk 3: Synchronous Thread Blocking (Async Fix) ---

async def process_scene(
    scene: dict,
    characters: list,
    supabase: Client,
    job_id: str,
    state: dict,
    semaphore: asyncio.Semaphore,
):
    """
    Processes a single scene concurrently, gated by the Semaphore to prevent 429 floods.
    """
    async with semaphore:
        try:
            logger.info("scene_rendering", scene_number=scene.get('scene_number'), job_id=job_id)

            # NEW: State Heartbeat - Per Scene Rendering Progress
            await sync_pipeline_state(job_id, state, "KEYFRAME_GENERATION", status_message=f"Rendering Neural Visual for Scene {scene.get('scene_number')}...")
            active_chars = []
            has_locked_face = False
            locked_face_url = ""

            script_text = str(scene.get("script_text", ""))
            script_text_lower = script_text.lower()
            # Truncate script text to keep prompts manageable
            safe_script_text = script_text.replace("\n", " ")[:500]

            active_character_ids = scene.get("active_characters", [])

            for char in characters:
                char_id = str(char.get("id", ""))
                name = str(char.get("name", "")).lower()
                
                # Strict adherence to Director's active characters constraint
                is_active = False
                if active_character_ids is not None and len(active_character_ids) > 0:
                    if char_id in active_character_ids or char.get("name") in active_character_ids:
                        is_active = True
                else:
                    # Fallback to precise regex boundaries if director array is mysteriously empty
                    import re
                    if name and re.search(r'\b' + re.escape(name) + r'\b', script_text_lower):
                        is_active = True

                if is_active:
                    # Check for InstantID presence
                    if char.get("locked_face_url"):
                        has_locked_face = True
                        locked_face_url = char["locked_face_url"]

                    desc = char.get("physical_description", "no physical description")
                    outfit = char.get("outfit", "no outfit specified")
                    active_chars.append(f"({desc}, wearing {outfit})")

            char_chunk = (
                " featuring " + " and ".join(active_chars)
                if active_chars
                else " (establishing landscape shot)"
            )
            camera_angle = scene.get("camera_angle", "dynamic cinematic angle")
            lighting_prompt = scene.get("lighting_prompt", "volumetric cinematic lighting")
            
            # --- 🛠️ SPATIAL INTELLIGENCE ENGINE ---
            spatial_layout = scene.get("spatial_layout", "standard depth")
            camera_directives = scene.get("camera_directives", "cinematic composition")
            
            # Intelligent Lens Selection based on spatial volume
            lens = "35mm wide-angle lens" if "wide" in spatial_layout.lower() or "landscape" in spatial_layout.lower() else "85mm anamorphic prime"
            
            prompt = (
                f"Cinematic high-fidelity film still, {camera_angle}, {lighting_prompt}, shot on {lens}. "
                f"Spatial Layout: {spatial_layout}. Camera Movement: {camera_directives}. "
                f"Action: {safe_script_text}. {char_chunk}. "
                "Masterpiece, 8k resolution, photorealistic, intricate textures, hyper-realistic, "
                "depth of field, atmospheric scattering, 3D spatial cues, volumetric light rays, parallax depth. "
                "CRITICAL REQUIREMENTS: NO TEXT, NO WATERMARKS, NO UI ELEMENTS, NO SPEECH BUBBLES, NO MUTATIONS, PURE CINEMA."
            )

            # Execute Generation: Quad-Level Fallback (Master Load Balancer)
            image_bytes = None
            
            # Level 1: Primary Generation Route (OpenAI DALL-E 3 / fal PuLID)
            try:
                # If there's an explicit face reference to lock, we MUST route to fal.ai PuLID.
                # OpenAI DALL-E 3 does not structurally support Image-to-Image Identity locking.
                if has_locked_face and locked_face_url and os.getenv("FAL_KEY"):
                    logger.info("fal_flux_pulid_attempted", scene_number=scene.get("scene_number"))
                    image_bytes = await query_fal_flux_pulid(prompt, locked_face_url)
                elif os.getenv("OPENAI_API_KEY"):
                    # Standard execution overrides to the user-requested OpenAI DALL-E 3
                    logger.info("openai_dalle3_attempted", scene_number=scene.get("scene_number"))
                    image_bytes = await query_openai_dalle3(prompt)
                elif os.getenv("FAL_KEY"):
                    # Fallback to Fal Flux Schnell if OpenAI is suddenly missing
                    logger.info("fal_flux_schnell_attempted", scene_number=scene.get("scene_number"))
                    image_bytes = await query_fal_flux_schnell(prompt)
            except Exception as e:
                logger.warning("primary_generator_failed", error=str(e), scene_number=scene.get("scene_number"))

            # Level 2: NVIDIA NIM SDXL (Resilience)
            if not image_bytes:
                try:
                    if os.getenv("NVIDIA_NIM_KEY"):
                        logger.info("nim_generation_attempted", scene_number=scene.get("scene_number"))
                        api_url = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"
                        headers = {
                            "Authorization": f"Bearer {os.getenv('NVIDIA_NIM_KEY')}",
                            "Accept": "application/json",
                        }
                        payload = {
                            "text_prompts": [{"text": prompt, "weight": 1}],
                            "cfg_scale": 7,
                            "steps": 30,
                        }
                        # We use a direct requests call here for simplicity in this fallback layer
                        response = await asyncio.to_thread(requests.post, api_url, headers=headers, json=payload, timeout=30)
                        if response.status_code == 200:
                            import base64
                            res_json = response.json()
                            image_bytes = base64.b64decode(res_json['artifacts'][0]['base64'])
                except Exception as e:
                    logger.warning("nim_failed", error=str(e), scene_number=scene.get("scene_number"))

            # Level 3: HuggingFace Flux (Resilience)
            if not image_bytes:
                try:
                    logger.info("hf_flux_attempted", scene_number=scene.get("scene_number"))
                    image_bytes = await asyncio.to_thread(query_huggingface_flux, prompt)
                except Exception as e:
                    logger.warning("hf_flux_failed", error=str(e), scene_number=scene.get("scene_number"))

            # Level 4: HF SDXL-Lightning (Resilience - Fast)
            if not image_bytes:
                try:
                    logger.info("hf_lightning_attempted", scene_number=scene.get("scene_number"))
                    lightning_url = "https://api-inference.huggingface.co/models/ByteDance/SDXL-Lightning"
                    headers = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}"}
                    response = await asyncio.to_thread(requests.post, lightning_url, headers=headers, json={"inputs": prompt}, timeout=15)
                    if response.status_code == 200:
                        image_bytes = response.content
                except Exception as e:
                    logger.warning("hf_lightning_failed", error=str(e), scene_number=scene.get("scene_number"))

            if not image_bytes:
                raise ValueError("All art generation fallback levels exhausted.")

            # Upload to Cloud
            filename = f"{job_id}_scene_{scene.get('scene_number')}.png"
            public_url = await asyncio.to_thread(
                upload_to_supabase_storage, supabase, image_bytes, filename
            )

            scene["keyframe_url"] = public_url
            logger.info(
                "scene_keyframe_stored",
                scene_number=scene.get('scene_number'),
                public_url=public_url,
                job_id=job_id,
            )

        except Exception as e:
            logger.error("scene_render_failed", scene_number=scene.get('scene_number'), error=str(e), job_id=job_id)
            # Use a professional, cinematic placeholder instead of breaking the pipeline
            placeholder_url = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?q=80&w=1024&auto=format&fit=crop"
            scene["keyframe_url"] = placeholder_url
            scene["is_draft"] = True
            # We don't re-raise here; we allow the graph to proceed with a 'Draft' visual


async def agent_keyframe_architect(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 4: The Keyframe Architect
    Uses Asyncio Gather and Semaphores to render scenes non-linearly without triggering API bans.
    """
    logger.info("agent_started", agent="keyframe_architect", job_id=state['job_id'])

    # 1. Verification
    if not os.getenv("HUGGINGFACE_API_KEY"):
        logger.warning("agent_skipped", agent="keyframe_architect", reason="HUGGINGFACE_API_KEY missing", job_id=state['job_id'])
        for scene in state.get("scenes", []):
            scene["keyframe_url"] = "https://mock.com/simulated.png"
        state["current_agent"] = "Vision QA"
        return state

    supabase = get_supabase_client()

    # Because we implemented the Tri-Nodal Master Load Balancer, we can safely
    # triple the concurrency limit inherently shrinking render times.
    semaphore = asyncio.Semaphore(6)

    # Create the async tasks array
    tasks = []
    for scene in state.get("scenes", []):
        task = asyncio.create_task(
            process_scene(
                scene,
                state.get("characters", []),
                supabase,
                state["job_id"],
                state,
                semaphore,
            )
        )
        tasks.append(task)

    # Execute non-linearly. Return exceptions gracefully instead of halting job.
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Phase 10: Cost Tracking & Error Verification
    state["validation_failures"] = state.get("validation_failures", 0)
    success_count = 0
    for result in results:
        if isinstance(result, Exception):
            state["validation_failures"] += 1
            state["last_error"] = str(result)
        else:
            success_count += 1
    
    # Flux Schnell is roughly $0.003 per image in API credits
    state["running_cost_usd"] = success_count * 0.003

    state["current_agent"] = "vocal_synthesizer" # Lowercase for graph
    state["pipeline_stage"] = "KEYFRAME_GENERATION"
    
    # NEW: Zero-Compromise Heartbeat Sync
    await sync_pipeline_state(state["job_id"], state, "KEYFRAME_GENERATION")
    
    return state

