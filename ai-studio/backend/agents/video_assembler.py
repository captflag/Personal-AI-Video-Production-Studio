import os
import asyncio
import structlog
import requests
import tempfile
import shutil
from typing import List
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.state import UniversalGraphState
from backend.utils_auth import get_supabase_client
from backend.utils_sync import sync_pipeline_state

logger = structlog.get_logger()

# --- Config ---
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "ai_studio_renders")
os.makedirs(OUTPUT_DIR, exist_ok=True)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def download_asset(url: str, local_path: str):
    """Downloads a public URL with explicit variable initialization."""
    response = None
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)
    finally:
        if response is not None:
            response.close()

async def agent_video_assembler(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 6: Video Assembler
    Downloads all scenes, stitches them via MoviePy, and uploads the final result.
    """
    job_id = state["job_id"]
    scenes = state.get("scenes", [])
    
    if not scenes:
        logger.warning("agent_no_input", agent="video_assembler", job_id=job_id)
        state["current_agent"] = "Project Finalization"
        return state

    logger.info("agent_started", agent="video_assembler", job_id=job_id)
    
    # Create a unique work directory for this job
    work_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    
    clips = []
    try:
        # 1. Download & Process Clips
        for scene in scenes:
            scene_num = scene.get("scene_number")
            
            # CRITICAL: Only assemble what the human approved
            if scene.get("status") != "APPROVED":
                logger.info("scene_skipped_not_approved", scene=scene_num, job_id=job_id)
                continue
                
            # High Fidelity: Pull the deepest processed video artifact (Interpolated -> Temporal -> Motion)
                
            aud_path = os.path.join(work_dir, f"scene_{scene_num}.mp3")
            await asyncio.to_thread(download_asset, aud_url, aud_path)
            audio = AudioFileClip(aud_path)
            
            # Precision Heartbeat: Update UI for each scene assembly
            await sync_pipeline_state(job_id, state, "FINAL_ASSEMBLY", status_message=f"Processing Scene {scene_num}/{len(scenes)} Video & Audio...")

            if motion_url and "FAILED" not in motion_url:
                # MOTION MODE: Use the SVD .mp4 clip
                vid_path = os.path.join(work_dir, f"scene_{scene_num}_motion.mp4")
                await asyncio.to_thread(download_asset, motion_url, vid_path)
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(vid_path).set_audio(audio)
            elif img_url and "FAILED" not in img_url:
                # STILL MODE: Fallback to animated stills
                img_path = os.path.join(work_dir, f"scene_{scene_num}.png")
                await asyncio.to_thread(download_asset, img_url, img_path)
                clip = ImageClip(img_path).set_duration(audio.duration).set_audio(audio)
            else:
                logger.warning("scene_skipped_no_visual", scene=scene_num, job_id=job_id)
                continue

            clip = clip.resize(newsize=(1024, 1024)).set_fps(24) 
            clips.append(clip)
            
        if not clips:
            raise ValueError("No valid clips to assemble.")

        # 2. Stitch & Render
        supabase = get_supabase_client()
        # Preliminary Sync update to prevent 15-min DLQ timeout during heavy render
        await asyncio.to_thread(
            lambda: supabase.table("jobs").update({"status": "RENDERING", "pipeline_stage": "ASSEMBLY"}).eq("id", job_id).execute()
        )
        
        final_video = concatenate_videoclips(clips, method="compose")
        final_path = os.path.join(work_dir, f"{job_id}_final.mp4")
        
        # Master Graduation: High-Bitrate H.264 rendering
        await sync_pipeline_state(job_id, state, "FINAL_ASSEMBLY", status_message="Rendering Cinematic Master (bitrate=8Mbps)...")
        logger.info("rendering_started", job_id=job_id, clips=len(clips))
        await asyncio.to_thread(
            final_video.write_videofile, 
            final_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            bitrate="8000k",
            preset="medium",
            # PERFORMANCE: Increased threads to 4 for faster Zero-GPU rendering
            threads=4, 
            logger=None
        )
        
        # 3. Upload to Supabase
        with open(final_path, "rb") as f:
            supabase.storage.from_("videos").upload(
                path=f"{job_id}_final.mp4",
                file=f,
                file_options={"content-type": "video/mp4"}
            )
            
        final_url = supabase.storage.from_("videos").get_public_url(f"{job_id}_final.mp4")
        
        # Success!
        state["video_url"] = final_url
        state["current_agent"] = "final_persistence"
        state["pipeline_stage"] = "FINAL_ASSEMBLY"
        # Zero-GPU CPU rendering is free ($0.0)
        state["running_cost_usd"] = 0.0
        
        logger.info("agent_completed", agent="video_assembler", job_id=job_id, url=final_url)
        
        # NEW: Zero-Compromise Heartbeat Sync
        await sync_pipeline_state(job_id, state, "FINAL_ASSEMBLY")
        
    except Exception as e:
        logger.error("agent_assembly_failed", error=str(e), job_id=job_id)
        state["last_error"] = str(e)
        state["validation_failures"] = state.get("validation_failures", 0) + 1
    finally:
        # Cleanup clips to release file handles
        for c in clips:
            try: c.close()
            except: pass
        
        # PERFORMANCE: Immediate Neural Garbage Collection (Self-Cleaning)
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.info("neural_cleanup_completed", job_id=job_id)
        except:
            pass
        if 'final_video' in locals():
            try: final_video.close()
            except: pass
        # Cleanup temporary files
        shutil.rmtree(work_dir, ignore_errors=True)

    return state
