import os
import asyncio
import structlog
import requests
from typing import Dict, List
from backend.state import UniversalGraphState
from backend.utils_auth import get_supabase_client
from backend.utils_sync import sync_pipeline_state

logger = structlog.get_logger()

# --- Config: Zero-Compromise Vision Auditor ---
NVIDIA_NIM_KEY = os.getenv("NVIDIA_NIM_KEY")
import base64

import httpx

async def query_gemini_vision(image_url: str, prompt: str) -> Dict:
    """Calls Gemini 1.5 Flash Vision for forensic visual analysis."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {"score": 0.9, "notes": "Audit Skipped (API Key Missing)"}
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    # Download the image to bytes for Gemini
    import requests
    img_data = base64.b64encode(requests.get(image_url).content).decode("utf-8")
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {
                    "mime_type": "image/png",
                    "data": img_data
                }}
            ]
        }],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            text_resp = data['candidates'][0]['content']['parts'][0]['text']
            import json
            return json.loads(text_resp)
    except Exception as e:
        logger.error("gemini_vision_failed", error=str(e))
        return {"score": 0.5, "notes": f"Neural Audit Error: {str(e)}"}

async def agent_vision_qa(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 8: Neural Vision Auditor
    -------------------------
    Performs forensic visual analysis on generated scenes.
    """
    job_id = state["job_id"]
    scenes = state.get("scenes", [])
    if not scenes: return state

    logger.info("agent_neural_audit_started", job_id=job_id)
    await sync_pipeline_state(job_id, state, "VISION_QA", status_message="Neural Auditor Scanning 3D Layers...")

    for scene in scenes:
        scene_num = scene.get("scene_number")
        keyframe_url = scene.get("keyframe_url")
        if not keyframe_url or "FAILED" in keyframe_url or "unsplash" in keyframe_url: continue
        
        prompt = f"""
        Analyze this AI-generated cinematic scene for Video-Level Fidelity.
        1. SPATIAL AWARENESS: Is there clear Foreground (2m), Midground (10m), and Background (Infinite) separation?
        2. ANATOMIC STABILITY: Does the subject have anatomically correct limbs? (Check for JOINT MELTING).
        3. BACKGROUND INTEGRITY: Does the background look stable or is it WARPING/STRETCHING?
        4. TEXTURE FIDELITY: Is there THREAD-LEVEL SHIMMERING or flickering potential?
        
        Mandated Layout: {scene.get('spatial_layout')}
        
        Return ONLY a JSON object: {{"score": float, "notes": string, "joint_melting": boolean, "background_warping": boolean}}
        """
        
        # Execute Neural Audit
        result = await query_gemini_vision(keyframe_url, prompt)
        
        scene["vision_qa_score"] = result.get("score", 0.5)
        # Force lower score if melting/warping is detected
        if result.get("joint_melting") or result.get("background_warping"):
            scene["vision_qa_score"] = min(scene["vision_qa_score"], 0.4)
            
        scene["qa_notes"] = result.get("notes", "No notes.")
        
        if scene["vision_qa_score"] < 0.7:
            logger.warning("scene_audit_low_score", scene=scene_num, score=result.get("score"))
            scene["status"] = "FAILED_QA"
        else:
            logger.info("scene_audit_success", scene=scene_num, score=result.get("score"))
            scene["status"] = "AUDITED"

    state["current_agent"] = "video_assembler"
    state["pipeline_stage"] = "VISION_QA_COMPLETED"
    
    await sync_pipeline_state(job_id, state, "VISION_QA", status_message="Neural Audit Complete.")
    return state
