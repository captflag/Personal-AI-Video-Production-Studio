import os
import structlog
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.state import UniversalGraphState

class MotionSchema(BaseModel):
    intensity_score: int = Field(description="A strictly calculated integer from 1 to 10 predicting the required physical speed/aggression of the scene. 1 = extreme slow-motion stillness, 10 = violent explosive fast action.")
    subject_action: str = Field(description="Explicit description of the main subject's kinetic limb movement (e.g. 'Legs extending and pushing off for leap', 'Arms swinging aggressively'). Focus on physical joint-level action.")
    kling_prompt: str = Field(description="Strict comma-separated keyword prompt optimized for Kling. Must include limbs-specific motion keywords.")
    cogvideo_prompt: str = Field(description="Narrative paragraph optimized for CogVideo. Must describe subject motion independently of background motion.")

logger = structlog.get_logger()

async def agent_motion_director(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 14: Advanced Hollywood Motion Director
    Engineers API-specific prompts based on dynamic intensity calculations and explicitly guards against AI morphological shape-shifting.
    """
    job_id = state.get("job_id")
    logger.info("agent_started", agent="motion_director", job_id=job_id)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("agent_skipped", agent="motion_director", reason="GROQ_API_KEY missing", job_id=job_id)
        state["current_agent"] = "keyframe_architect"
        return state

    # Force utilizing the high-fidelity JSON-expert model
    llm = ChatGroq(
        api_key=api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )

    structured_llm = llm.with_structured_output(MotionSchema)
    scenes = state.get("scenes", [])

    for scene in scenes:
        scene_num = scene.get("scene_number")
        script_text = scene.get("script_text", "No script provided.")
        camera_angle = scene.get("camera_angle", "Standard angle.")
        
        prompt_text = f"""You are an elite Hollywood Technical Animator building Image-To-Video API prompts.

=== MOTION LAYER CRITICAL RULES ===
1. SUBJECT-LAYER MOTION: Identify the main subject and dictate their specific limb actions (leaps, leaps, joint movements).
2. KINETIC INDEPENDENCE: Subject motion MUST be described separately from global camera or background motion to simulate a 'Motion Brush' effect.
3. PREVENT STATIC CHARACTERS: Direct the AI to ensure limbs move significantly matching the script.
4. PREVENT SHAPE-SHIFTING: Append strict physical consistency guards to all narrative outputs.

Input Context for Scene {scene_num}:
Script: {script_text}
Camera Angle: {camera_angle}

Write the Kling (Keyword Dense) and CogVideo (Narrative Paragraph) prompts. Focus deeply on exactly how the limbs move relative to the static background.
"""

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6))
        async def _execute_motion_llm():
            return await structured_llm.ainvoke(prompt_text)

        try:
            result: MotionSchema = await _execute_motion_llm()
            # Store the classic generic prompt generically, but save the advanced ones
            scene["motion_intensity"] = result.intensity_score
            scene["subject_action"] = result.subject_action
            scene["motion_prompt_kling"] = result.kling_prompt
            scene["motion_prompt_cogvideo"] = result.cogvideo_prompt
            
            # Universal fallback string logging
            scene["motion_prompt"] = f"Action [{result.subject_action}]: {result.cogvideo_prompt}"
            logger.info("motion_computed", job_id=job_id, scene=scene_num, intensity=result.intensity_score)
        except Exception as e:
            logger.error("agent_llm_failed", agent="motion_director", error=str(e), job_id=job_id, scene=scene_num)
            scene["motion_prompt"] = "Cinematic video, character moving gently, camera tracks."
            scene["subject_action"] = "Gentle movement"
            scene["motion_prompt_kling"] = "Cinematic video, movement, standard tracking."
            scene["motion_prompt_cogvideo"] = "Cinematic video with beautiful visuals. Character moves gently. Perfect anatomical structure."
            scene["motion_intensity"] = 5

    state["running_cost_usd"] += 0.002
    
    logger.info("agent_completed", agent="motion_director", job_id=job_id)
    state["current_agent"] = "keyframe_architect"
    state["pipeline_stage"] = "MOTION_DIRECTOR"
    return state
