import os
import structlog
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.state import UniversalGraphState

class HookAnalysis(BaseModel):
    score: int = Field(description="Retention probability score from 1 to 10 (10 being impossible to click away from)")
    critique: str = Field(description="Mathematical explanation of why it hooks or fails.")
    improved_script_text: str = Field(description="If score < 7, provide a rewritten Scene 1 that is inherently more visually arresting.")

logger = structlog.get_logger()


async def agent_hook_analyst(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 3: Hook Analyst
    Analyzes Scene 1 to guarantee high viewer retention for platforms like YouTube Shorts.
    """
    logger.info("agent_started", agent="hook_analyst", job_id=state["job_id"])
    
    # Extract only scene 1
    scenes = state.get("scenes") or []
    scene_1 = next((s for s in scenes if s.get("scene_number") == 1), None)
    
    if not scene_1:
        logger.warning("agent_no_input", agent="hook_analyst", job_id=state["job_id"], reason="no scenes in state")
        return state # Edge case safety
        
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.3
    )
    
    structured_llm = llm.with_structured_output(HookAnalysis)
    
    prompt_text = f"""You are a master of YouTube Retention Analytics.
    
Here is the opening scene (Scene 1) of the video script:
TEXT: {scene_1['script_text']}
CAMERA: {scene_1['camera_angle']}

Score this scene from 1 to 10 on its ability to completely halt a scrolling user within the first 3 seconds.
If it involves long slow pans or boring dialogue without an immediate visual or narrative conflict, score it < 5.
If it drops the viewer instantly into extreme action, profound mystery, or intense emotion, score it > 8.

If your score is less than 7, rewrite the script text to be instantly hooking. If it is 7 or above, just repeat the original text.
"""
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _execute_hook_llm():
        return await structured_llm.ainvoke(prompt_text)

    try:
        # Use ainvoke for non-blocking analysis in the ARQ worker
        result: HookAnalysis = await _execute_hook_llm()
    except Exception as e:
        logger.error("agent_llm_failed", agent="hook_analyst", error=str(e), job_id=state["job_id"])
        state["last_error"] = str(e)
        state["validation_failures"] = state.get("validation_failures", 0) + 1
        return state

    # Mutate State
    for s in state['scenes']:
        if s["scene_number"] == 1:
            s["hook_score"] = result.score
            if result.score < 7:
                logger.info("hook_rewrite_triggered", job_id=state["job_id"], score=result.score)
                s["script_text"] = result.improved_script_text

    # Phase 10: Cost Tracking
    state["running_cost_usd"] = 0.001
                
    logger.info("agent_completed", agent="hook_analyst", job_id=state["job_id"])
    state["current_agent"] = "hook_analyst" # Keeping it here for router to catch
    state["pipeline_stage"] = "CP1_CHECKPOINT"
    return state
