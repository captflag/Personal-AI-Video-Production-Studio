import os
import structlog
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.state import UniversalGraphState

# --- Structured Outputs ---
class SceneCinematography(BaseModel):
    scene_number: int
    camera_angle: str = Field(
        description="Specific camera direction: e.g. 'Low angle, extreme wide shot, tracking push-in. Arri Alexa 65mm'"
    )
    lighting_prompt: str = Field(
        description="Strict lighting mechanics: e.g. 'HDR rim light, cinematic chiaroscuro, volumetric rays, ray-traced shadows'"
    )
    light_source_origin: str = Field(
        description="Physical 3D position of the primary light source (e.g. 'Backlight from 180 degrees', 'Top-down sun at 90 degrees'). Essential for HDR light-wrapping."
    )

class CinematographerOutput(BaseModel):
    shots: List[SceneCinematography]


# --- Agent 2: The Cinematographer ---
logger = structlog.get_logger()


async def agent_cinematographer(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 2: Cinematographer
    Reads the director's raw scenes and injects highly technical camera and lighting instructions.
    """
    job_id = state.get("job_id")
    logger.info("agent_started", agent="cinematographer", job_id=job_id)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("agent_skipped", agent="cinematographer", reason="GROQ_API_KEY missing", job_id=job_id)
        state["current_agent"] = "Hook Analyst"
        return state

    llm = ChatGroq(
        api_key=api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.5,  # Lower temp for more technical consistency
    )

    structured_llm = llm.with_structured_output(CinematographerOutput)

    scenes = state.get("scenes", [])
    if not scenes:
        logger.warning("agent_no_input", agent="cinematographer", job_id=job_id, reason="no scenes in state")
        state["current_agent"] = "Hook Analyst"
        return state

    # We pass the scene script text mapped to numbers
    script_context = "\n".join(
        [f"Scene {s.get('scene_number')}: {s.get('script_text')}" for s in scenes]
    )

    prompt_text = f"""You are an Oscar-winning Cinematographer.

=== DYNAMIC HDR LIGHTING CRITICALS ===
1. LIGHT ORIGIN: Explicitly define the 3D position of the primary light source (e.g. 'Back-left at 135 degrees').
2. DYNAMIC WRAPPING: Describe exactly how the rim light and shadows shift during subject motion (e.g. 'rim light follows shoulder as character leaps').
3. RAY-TRACED FIDELITY: Use technical photography terms like 'Subsurface scattering', 'Volumetric rays', and 'HDR shadows'.

Here is the script context:
{script_context}
"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _execute_cinematographer_llm():
        return await structured_llm.ainvoke(prompt_text)

    try:
        # Use ainvoke to prevent blocking the worker loop
        result: CinematographerOutput = await _execute_cinematographer_llm()

        # Merge the answers back into the universal state scenes
        # We index by scene_number to ensure perfect mapping
        for shot in result.shots:
            for s in scenes:
                if s.get("scene_number") == shot.scene_number:
                    s["camera_angle"] = shot.camera_angle
                    s["lighting_prompt"] = shot.lighting_prompt
                    s["light_source_origin"] = shot.light_source_origin

    except Exception as e:
        logger.error("agent_llm_failed", agent="cinematographer", error=str(e), job_id=job_id)
        state["last_error"] = str(e)
        state["validation_failures"] = state.get("validation_failures", 0) + 1
        return state

    # Phase 10: Cost Tracking ($0.001 approx)
    state["running_cost_usd"] = 0.001
    
    logger.info("agent_completed", agent="cinematographer", job_id=job_id)
    state["current_agent"] = "hook_analyst" # Lowercase for graph consistency
    state["pipeline_stage"] = "HOOK_ANALYSIS"
    return state

