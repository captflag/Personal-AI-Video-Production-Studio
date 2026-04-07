import os
import cv2
import asyncio
import httpx
import tempfile
import structlog
from backend.state import UniversalGraphState
from backend.utils_auth import get_supabase_client
from backend.utils_sync import sync_pipeline_state

logger = structlog.get_logger()

async def agent_temporal_consistency(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 12: Temporal Consistency Engine
    Analyzes generated motion video and removes harsh contrast/lighting flickers 
    across the time-axis using Exponential Moving Average Deflickering.
    """
    job_id = state["job_id"]
    scenes = state.get("scenes", [])
    supabase = get_supabase_client()
    
    for scene in scenes:
        motion_url = scene.get("motion_video_url")
        if not motion_url or "FAILED" in motion_url:
            continue
            
        scene_num = scene.get("scene_number")
        
        try:
            await sync_pipeline_state(job_id, state, "TEMPORAL_CONSISTENCY", status_message=f"Deflickering Scene {scene_num} using Temporal Alignment...")
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(motion_url, timeout=60)
                resp.raise_for_status()
                video_data = resp.content
                
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f_in, \
                 tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f_out:
                
                f_in.write(video_data)
                f_in.close()
                f_out.close()
                
                # Math deflicker logic (OpenCV)
                cap = cv2.VideoCapture(f_in.name)
                fps = cap.get(cv2.CAP_PROP_FPS) or 24
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(f_out.name, fourcc, fps, (w, h))
                
                ret, prev_frame = cap.read()
                if not ret:
                    raise ValueError("No frames in video for temporal consistency.")
                    
                out.write(prev_frame)
                
                while True:
                    ret, curr_frame = cap.read()
                    if not ret: break
                    
                    # Temporal Smoothing (Exponential Moving Average Blend)
                    # For performance and structural preservation, we apply an 80/20 alpha pass
                    blended = cv2.addWeighted(curr_frame, 0.85, prev_frame, 0.15, 0)
                    out.write(blended)
                    prev_frame = blended
                    
                cap.release()
                out.release()
                
                # Final Pass via MoviePy for browser-compatible H264 packaging
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(f_out.name)
                final_out_path = f_out.name + "_final.mp4"
                await asyncio.to_thread(
                    clip.write_videofile, final_out_path, fps=fps, codec="libx264", audio=False, logger=None, preset="medium", threads=4
                )
                
                with open(final_out_path, "rb") as f:
                    final_bytes = f.read()
                
                # Critical bug fix: Release Windows file locks before garbage collection
                clip.close()
                os.unlink(f_in.name)
                os.unlink(f_out.name)
                os.unlink(final_out_path)
                
            filename = f"{job_id}_scene_{scene_num}_temporal.mp4"
            supabase.storage.from_("videos").upload(filename, final_bytes, file_options={"content-type": "video/mp4", "x-upsert": "true"})
            
            scene["temporal_video_url"] = supabase.storage.from_("videos").get_public_url(filename)
            logger.info("temporal_consistency_complete", scene=scene_num)
            
        except Exception as e:
            logger.error("temporal_consistency_failed", scene=scene_num, error=str(e))
            # Safe Fallback
            scene["temporal_video_url"] = motion_url
            
    state["current_agent"] = "motion_interpolator"
    return state
