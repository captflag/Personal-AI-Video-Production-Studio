import os
import cv2
import numpy as np
import asyncio
import httpx
import tempfile
import structlog
from backend.state import UniversalGraphState
from backend.utils_auth import get_supabase_client
from backend.utils_sync import sync_pipeline_state

logger = structlog.get_logger()

async def agent_motion_interpolator(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 13: Motion Interpolator Engine
    Uses Python Dense Optical Flow (Farneback) to synthesize 
    artificial in-between frames, essentially doubling the frame rate
    and providing ultra-smooth output (24fps -> 48fps standard).
    """
    job_id = state["job_id"]
    scenes = state.get("scenes", [])
    supabase = get_supabase_client()
    
    for scene in scenes:
        # Takes the temporally stabilized video (or falls back to raw motion)
        video_url = scene.get("temporal_video_url") or scene.get("motion_video_url")
        if not video_url or "FAILED" in video_url:
            continue
            
        scene_num = scene.get("scene_number")
        
        try:
            await sync_pipeline_state(job_id, state, "MOTION_INTERPOLATION", status_message=f"Optically interpolating Scene {scene_num} vectors...")
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(video_url, timeout=60)
                resp.raise_for_status()
                video_data = resp.content
                
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f_in, \
                 tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f_out:
                
                f_in.write(video_data)
                f_in.close()
                f_out.close()
                
                # Math Interpolation Logic (OpenCV Farneback)
                cap = cv2.VideoCapture(f_in.name)
                fps = cap.get(cv2.CAP_PROP_FPS) or 24
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                target_fps = fps * 2
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(f_out.name, fourcc, target_fps, (w, h))
                
                ret, prev_frame = cap.read()
                if not ret:
                    raise ValueError("No frames in video for optical interpolation.")
                    
                prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                out.write(prev_frame)
                
                while True:
                    ret, curr_frame = cap.read()
                    if not ret: break
                    
                    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
                    
                    # Compute Dense Optical Flow
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, curr_gray, None, 
                        pyr_scale=0.5, levels=3, winsize=15, 
                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                    )
                    
                    # Synthesize halfway frame (T=0.5)
                    h_flow, w_flow = flow.shape[:2]
                    flow_map = -flow / 2.0
                    flow_map[:,:,0] += np.arange(w_flow)
                    flow_map[:,:,1] += np.arange(h_flow)[:,np.newaxis]
                    flow_map_32f = flow_map.astype(np.float32)
                    
                    half_frame = cv2.remap(prev_frame, flow_map_32f, None, cv2.INTER_LINEAR)
                    
                    # Output synthesized + real frame
                    out.write(half_frame)
                    out.write(curr_frame)
                    
                    prev_frame = curr_frame
                    prev_gray = curr_gray
                    
                cap.release()
                out.release()
                
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(f_out.name)
                final_out_path = f_out.name + "_final.mp4"
                await asyncio.to_thread(
                    clip.write_videofile, final_out_path, fps=target_fps, codec="libx264", audio=False, logger=None, preset="medium", threads=4
                )
                
                with open(final_out_path, "rb") as f:
                    final_bytes = f.read()
                    
                # Critical bug fix: Release Windows file locks before garbage collection
                clip.close()
                os.unlink(f_in.name)
                os.unlink(f_out.name)
                os.unlink(final_out_path)
                
            filename = f"{job_id}_scene_{scene_num}_interpolated.mp4"
            supabase.storage.from_("videos").upload(filename, final_bytes, file_options={"content-type": "video/mp4", "x-upsert": "true"})
            
            scene["interpolated_video_url"] = supabase.storage.from_("videos").get_public_url(filename)
            logger.info("motion_interpolation_complete", scene=scene_num, fps=target_fps)
            
        except Exception as e:
            logger.error("motion_interpolation_failed", scene=scene_num, error=str(e))
            # Safe Fallback to temporal video
            scene["interpolated_video_url"] = video_url
            
    state["current_agent"] = "vision_qa"
    state["pipeline_stage"] = "INTERPOLATION"
    return state
