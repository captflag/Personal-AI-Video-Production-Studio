import os
import asyncio
import structlog
import requests
from typing import List
from backend.state import UniversalGraphState
from backend.utils_auth import get_supabase_client
from backend.utils_sync import sync_pipeline_state

logger = structlog.get_logger()

# --- Config ---
# For a Zero-GPU setup, we use HuggingFace Inference Endpoints or public Spaces
FAL_WAV2LIP_URL = "https://fal.run/fal-ai/wav2lip"

async def query_fal_wav2lip(video_url: str, audio_url: str) -> str:
    """Calls fal-ai/wav2lip for high-fidelity voice-to-mouth synchronization."""
    api_key = os.getenv("FAL_KEY")
    if not api_key: return None
    
    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    payload = {"video_url": video_url, "audio_url": audio_url}
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(FAL_WAV2LIP_URL, headers=headers, json=payload, timeout=300)
            res.raise_for_status()
            data = res.json()
            return data.get("video", {}).get("url")
    except Exception as e:
        logger.error("fal_wav2lip_failed", error=str(e))
        return None

async def agent_lip_sync(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 7: Neural Lip-Sync Specialist
    Synchronizes Motion Video with Vocal Narration for absolute physical realism.
    """
    job_id = state["job_id"]
    scenes = state.get("scenes", [])
    if not scenes: return state

    logger.info("agent_neural_lipsync_started", job_id=job_id)
    await sync_pipeline_state(job_id, state, "LIP_SYNC", status_message="Synchronizing Neural Visemes...")

    for scene in scenes:
        scene_num = scene.get("scene_number")
        motion_url = scene.get("motion_video_url")
        audio_url = scene.get("audio_url")
        
        if not motion_url or not audio_url or "FAILED" in motion_url or "FAILED" in audio_url:
            continue
            
        try:
            # Execute Neural Lip Sync
            sync_url = await query_fal_wav2lip(motion_url, audio_url)
            
            if sync_url:
                scene["lip_sync_video_url"] = sync_url
                scene["status"] = "SYNCHRONIZED"
                logger.info("scene_lipsync_success", scene=scene_num)
            else:
                scene["lip_sync_video_url"] = motion_url # Fallback to unsynced motion
                logger.warning("scene_lipsync_fallback", scene=scene_num)
                
        except Exception as e:
            logger.error("sad_talker_failed", error=str(e), scene=scene_num)
        
    state["pipeline_stage"] = "LIP_SYNC_COMPLETED"
    state["current_agent"] = "video_assembler"
    
    await sync_pipeline_state(job_id, state, "LIP_SYNC_COMPLETED")
    return state
