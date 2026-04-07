from typing import TypedDict, List, Optional, Dict, Any
import operator
from typing import Annotated

# --- Pydantic Data Models (Sub-schemas) ---
# Used for deep structuring of lists within the state

class Character(TypedDict):
    id: str
    name: str
    physical_description: str
    outfit: str
    locked_face_url: Optional[str]
    voice_id: Optional[str]

class Scene(TypedDict):
    scene_number: int
    script_text: str
    camera_angle: Optional[str]
    lighting_prompt: Optional[str]
    hook_score: Optional[int]
    keyframe_url: Optional[str]
    motion_prompt: Optional[str]
    motion_intensity: Optional[int]
    motion_prompt_kling: Optional[str]
    motion_prompt_cogvideo: Optional[str]
    audio_url: Optional[str]
    motion_video_url: Optional[str]
    lip_sync_video_url: Optional[str]
    temporal_video_url: Optional[str]
    interpolated_video_url: Optional[str]
    video_url: Optional[str]

# --- The Master LangGraph State ---
# This is physically passed back and forth between all 11 Agents

class UniversalGraphState(TypedDict):
    """
    The mathematical heartbeat of the AI Video Studio pipeline.
    """
    job_id: str
    telegram_chat_id: str
    
    # User the raw 5-word seed prompt
    raw_prompt: str
    
    # Agent 11 Context Loads
    memory_context: Optional[str] 
    
    # Agent 1 (Director) Outputs
    characters: List[Character]
    scenes: List[Scene]
    
    # Validation & DLQ Flags
    current_agent: str
    pipeline_stage: str # Mapping to DB stages (CP1_SCRIPT, CP2_RENDER, etc.)
    validation_failures: Annotated[int, operator.add]
    last_error: Optional[str]
    
    # Final Artifacts
    video_url: Optional[str]
    
    # Costs (Instrumented in Phase 10)
    running_cost_usd: Annotated[float, operator.add]
