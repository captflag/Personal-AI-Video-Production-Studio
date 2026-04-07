import os
import structlog
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.state import UniversalGraphState

# --- 1. Structured Output Schema ---
# Forces Llama-3 to respond perfectly in JSON without regex hacking

class CharacterSchema(BaseModel):
    id: str = Field(description="Unique string ID like 'char_1'")
    name: str = Field(description="Character's full name")
    physical_description: str = Field(description="Crucial physiological details (age, race, hair, unique scars). MUST be highly specific for Stable Diffusion.")
    outfit: str = Field(description="Clothing description for continuity tracking.")

class SceneSchema(BaseModel):
    scene_number: int = Field(description="Sequential 1-12")
    script_text: str = Field(description="The physical dialogue and action blocking to occur in the scene.")
    spatial_layout: str = Field(description="Detailed 3D composition: Foreground vs Midground vs Background. Define exactly where the character is standing relative to the camera.")
    camera_directives: str = Field(description="Cinematic movement instructions like 'Dolly-In', 'Slow Parallax Pan', or 'Wide Angle Low Perspective' to emphasize 3D volume.")

class DirectorOutput(BaseModel):
    characters: List[CharacterSchema]
    scenes: List[SceneSchema]

# --- 2. The Agent Logic ---

logger = structlog.get_logger()


async def agent_director(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 1: The Director
    Reads the 5-word prompt and expands it into characters and a 12-scene script.
    """
    logger.info("agent_started", agent="director", job_id=state["job_id"])
    
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.7
    )
    
    structured_llm = llm.with_structured_output(DirectorOutput)
    
    prompt_text = f"""You are a master Hollywood Director. 
The user has provided a barebones concept: "{state['raw_prompt']}"

Your job is to expand this into a production-ready script with extreme SPATIAL AWARENESS.
1. Invent exactly 1-3 highly detailed characters. Define their physical design for Stable Diffusion.
2. Write a 3-to-6 scene script.
3. For every scene, you MUST define the SPATIAL LAYOUT: explicitly describe what is in the Foreground, Midground, and Background. 
4. Include CAMERA DIRECTIVES to emphasize 3D depth (e.g., dolly-in, parallax pan, low wide perspective).

Previous Episode Context (if any):
{state.get('memory_context', 'None')}
"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _execute_director_llm():
        return await structured_llm.ainvoke(prompt_text)

    try:
        # Use ainvoke for async compatibility with LangGraph and ARQ
        result: DirectorOutput = await _execute_director_llm()
    except Exception as e:
        logger.error("agent_llm_failed", agent="director", error=str(e), job_id=state["job_id"])
        state["last_error"] = str(e)
        state["validation_failures"] = state.get("validation_failures", 0) + 1
        return state
    
    # Map back to state
    state["characters"] = [
        char.model_dump() if hasattr(char, "model_dump") else char.dict()
        for char in result.characters
    ]
    state["scenes"] = [
        {
            "scene_number": s.scene_number,
            "script_text": s.script_text,
            "spatial_layout": s.spatial_layout,
            "camera_directives": s.camera_directives,
            "camera_angle": None,
            "lighting_prompt": None,
            "hook_score": None,
            "keyframe_url": None,
            "video_url": None,
            "audio_url": None
        } for s in result.scenes
    ]
    
    # Phase 10: Cost Tracking ($0.002 approx for Llama-3-70b large prompt)
    state["running_cost_usd"] = 0.002
    
    logger.info(
        "agent_completed", agent="director", job_id=state["job_id"],
        scenes=len(state["scenes"]), characters=len(state["characters"])
    )
    state["current_agent"] = "cinematographer" # Lowercase to match graph node
    state["pipeline_stage"] = "STORYBOARDING"
    return state
