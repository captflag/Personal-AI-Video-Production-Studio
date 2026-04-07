import os
import asyncio
from backend.utils_sync import sync_pipeline_state
import structlog
from io import BytesIO
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential
from supabase import Client
from backend.utils_auth import get_supabase_client
from backend.state import UniversalGraphState
from elevenlabs.client import AsyncElevenLabs
import edge_tts

logger = structlog.get_logger()

# --- Config ---
VOICE_MAP = {
    "default": "Antoni", # ElevenLabs default
    "edge_default": "en-US-GuyNeural" # High-quality Edge-TTS neural voice
}

def upload_audio_to_supabase(supabase: Client, audio_bytes: bytes, filename: str) -> str:
    """
    Pushes the generated .mp3 to the 'audio' bucket in Supabase.
    """
    try:
        # Validate bytes before upload
        if not audio_bytes or len(audio_bytes) < 10:
            raise ValueError(f"Invalid audio bytes for {filename}: length={len(audio_bytes)}")

        # Attempt to upload to 'audio' bucket
        supabase.storage.from_("audio").upload(
            path=filename,
            file=audio_bytes,
            file_options={"content-type": "audio/mpeg", "x-upsert": "true"},
        )
    except Exception as e:
        logger.warning("audio_upload_failed", filename=filename, error=str(e))
        # Don't reference local variables that might not exist in lower-level libraries
        raise
    
    return supabase.storage.from_("audio").get_public_url(filename)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def synthesize_elevenlabs(text: str, api_key: str) -> bytes:
    """
    Uses ElevenLabs Async client with Turbo v2.5 Hybrid Mastering.
    """
    from elevenlabs import VoiceSettings
    client = AsyncElevenLabs(api_key=api_key)
    
    # Convert generator to bytes with High-Fidelity Settings
    audio_generator = await client.generate(
        text=text,
        voice=VOICE_MAP["default"],
        model="eleven_turbo_v2_5",
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True
        )
    )
    audio_bytes = b""
    async for chunk in audio_generator:
        audio_bytes += chunk
    return audio_bytes


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def synthesize_edgetts(text: str) -> bytes:
    """
    Uses edge-tts (free) as a fallback.
    """
    communicate = edge_tts.Communicate(text, VOICE_MAP["edge_default"])
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes


async def process_voiceover(
    scene: dict,
    job_id: str,
    state: dict,
    supabase: Client,
    elevenlabs_key: str,
    semaphore: asyncio.Semaphore,
    scene_idx: int,
    total_scenes: int
):
    """
    Synthesizes audio for a single scene and uploads it.
    """
    async with semaphore:
        scene_num = scene.get("scene_number")
        text = scene.get("script_text", "")
        if not text or (scene.get("audio_url") and "FAILED" not in scene.get("audio_url", "")):
            logger.info("vocal_synthesis_skipped", scene=scene_num, reason="Audio already exists")
            return

        logger.info("vocal_synthesis_started", scene_number=scene_num, job_id=job_id)
        
        # Precision Heartbeat: Update UI for each scene
        await sync_pipeline_state(job_id, state, "VOCAL_SYNTHESIS", status_message=f"Vocalizing Neural Script {scene_idx + 1}/{total_scenes}...")
        
        try:
            if elevenlabs_key:
                audio_bytes = await synthesize_elevenlabs(text, elevenlabs_key)
                logger.debug("voice_provider_used", provider="elevenlabs", scene=scene_num)
            else:
                audio_bytes = await synthesize_edgetts(text)
                logger.debug("voice_provider_used", provider="edge-tts", scene=scene_num)

            # Upload to Supabase
            filename = f"{job_id}_scene_{scene_num}.mp3"
            public_url = await asyncio.to_thread(
                upload_audio_to_supabase, supabase, audio_bytes, filename
            )
            
            scene["audio_url"] = public_url
            logger.info("vocal_synthesis_completed", scene_number=scene_num, url=public_url)
            
        except Exception as e:
            logger.error("vocal_synthesis_failed", scene_number=scene_num, error=str(e), job_id=job_id)
            scene["audio_url"] = "AUDIO_FAILED"


async def agent_vocal_synthesizer(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 5: Vocal Synthesizer
    Generates high-quality narration for each scene.
    """
    job_id = state["job_id"]
    scenes = state.get("scenes", [])
    
    if not scenes:
        logger.warning("agent_no_input", agent="vocal_synthesizer", job_id=job_id)
        state["current_agent"] = "Audio-Visual Sync" # Next agent placeholder
        return state

    # Supabase Setup
    supabase = get_supabase_client()

    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    
    # Process scenes in parallel (concurrency limited to 3 to avoid rate limits)
    semaphore = asyncio.Semaphore(3)
    
    tasks = [
        process_voiceover(scene, job_id, state, supabase, elevenlabs_key, semaphore, idx, len(scenes))
        for idx, scene in enumerate(scenes)
        if scene.get("status") == "APPROVED"
    ]
    
    await asyncio.gather(*tasks)
    
    # Phase 10: Cost Tracking (Approx 1k chars = $0.05 on ElevenLabs)
    total_chars = sum(len(s.get("script_text", "")) for s in scenes)
    if elevenlabs_key:
        state["running_cost_usd"] = (total_chars / 1000) * 0.05
    else:
        state["running_cost_usd"] = 0.0 # Edge-TTS is free
    
    state["current_agent"] = "lip_sync"
    state["pipeline_stage"] = "VOCAL_SYNTHESIS"
    
    # NEW: Zero-Compromise Heartbeat Sync
    await sync_pipeline_state(job_id, state, "VOCAL_SYNTHESIS")
    
    logger.info("agent_completed", agent="vocal_synthesizer", job_id=job_id, cost=state["running_cost_usd"])
    return state
