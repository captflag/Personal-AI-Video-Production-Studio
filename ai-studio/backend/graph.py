import os
import requests
import structlog
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from backend.state import UniversalGraphState
from backend.agents.director import agent_director
from backend.agents.cinematographer import agent_cinematographer
from backend.agents.hook_analyst import agent_hook_analyst
from backend.agents.keyframe_architect import agent_keyframe_architect
from backend.agents.vocal_synthesizer import agent_vocal_synthesizer
from backend.agents.video_assembler import agent_video_assembler
from backend.agents.lip_sync_agent import agent_lip_sync
from backend.agents.video_alchemist import agent_video_alchemist
from backend.agents.vision_qa import agent_vision_qa
from backend.agents.temporal_consistency import agent_temporal_consistency
from backend.agents.motion_interpolator import agent_motion_interpolator
from backend.agents.motion_director import agent_motion_director
from backend.db import get_pool
from backend.utils_auth import get_supabase_client

logger = structlog.get_logger()


async def cp1_webhook(state: UniversalGraphState) -> UniversalGraphState:
    """
    Checkpoint 1: Script & Characters.
    Persists characters/scenes to Supabase and notifies n8n.
    """
    job_id = state.get("job_id")
    logger.info("checkpoint_1_reached", job_id=job_id)

    # Use high-performance asyncpg pool if available
    pool = await get_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                # 1. Persist Characters
                chars = state.get("characters", [])
                if chars:
                    char_data = [
                        (job_id, c.get("name"), c.get("physical_description"), c.get("outfit"))
                        for c in chars
                    ]
                    await conn.executemany(
                        "INSERT INTO characters (job_id, name, physical_description, outfit) VALUES ($1, $2, $3, $4)",
                        char_data
                    )

                # 2. Persist Scenes
                scenes = state.get("scenes", [])
                if scenes:
                    scene_data = [
                        (job_id, s.get("scene_number"), s.get("script_text"), s.get("camera_angle"),
                         s.get("lighting_prompt"), s.get("hook_score"), "CP1_SCRIPT")
                        for s in scenes
                    ]
                    await conn.executemany(
                        """INSERT INTO scenes (job_id, scene_number, script_text, camera_angle, lighting_prompt, hook_score, pipeline_stage)
                           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                        scene_data
                    )

                # Update Job Status
                await conn.execute(
                    "UPDATE jobs SET status = 'HITL_PAUSE', pipeline_stage = 'CP1_SCRIPT' WHERE id = $1",
                    job_id
                )
            logger.info("asyncpg_state_persisted", job_id=job_id, scenes=len(scenes), characters=len(chars))
        except Exception as e:
            logger.error("asyncpg_persist_failed", job_id=job_id, error=str(e))
    else:
        # --- Fallback to Supabase REST if Pool is Missing ---
        try:
            supabase = get_supabase_client()
            for char in state.get("characters", []):
                supabase.table("characters").insert({
                    "job_id": job_id, "name": char.get("name"),
                    "physical_description": char.get("physical_description"),
                    "outfit": char.get("outfit"),
                }).execute()
            for scene in state.get("scenes", []):
                supabase.table("scenes").insert({
                    "job_id": job_id, "scene_number": scene.get("scene_number"),
                    "script_text": scene.get("script_text"), "camera_angle": scene.get("camera_angle"),
                    "lighting_prompt": scene.get("lighting_prompt"), "hook_score": scene.get("hook_score"),
                    "pipeline_stage": "CP1_SCRIPT",
                }).execute()
            supabase.table("jobs").update({"status": "HITL_PAUSE", "pipeline_stage": "CP1_SCRIPT"}).eq("id", job_id).execute()
            logger.info("supabase_rest_persisted", job_id=job_id)
        except Exception as e:
            logger.error("supabase_persist_failed", job_id=job_id, error=str(e))
    # --- Fire Webhook (opt-in: set N8N_WEBHOOK_URL; omit to skip and avoid noisy errors) ---
    webhook_url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    if webhook_url:
        payload = {
            "body": {
                "job_id": job_id,
                "stage": "CP1_SCRIPT",
                "scenes": len(state.get("scenes", [])),
                "characters": len(state.get("characters", [])),
            }
        }
        try:
            requests.post(webhook_url, json=payload, timeout=5)
            logger.info("n8n_webhook_fired", job_id=job_id, stage="CP1_SCRIPT")
        except Exception as e:
            logger.warning("n8n_webhook_failed", job_id=job_id, error=str(e))

    return state


def hook_router(state: UniversalGraphState) -> str:
    """Conditional Edge: Loops backward if Hook Analyst rewrote Scene 1."""
    scenes = state.get("scenes", [])
    scene_1 = next(
        (s for s in scenes if s.get("scene_number") == 1),
        None,
    )

    # If a rewrite occurred, we force the score up so it acts as an exit flag
    hook_score = scene_1.get("hook_score") if scene_1.get("hook_score") is not None else 10
    if scene_1 and hook_score < 7:
        logger.info("hook_router_loopback", job_id=state.get("job_id"))
        scene_1["hook_score"] = 10  # Prevent infinite DAG loops
        return "cinematographer"
    return "checkpoint_1"


def qa_router(state: UniversalGraphState) -> str:
    """
    Conditional Edge: Routes to re-shoot if visual quality is low.
    Implements a 1-time 'Quality Retry' per job.
    """
    job_id = state.get("job_id")
    scenes = state.get("scenes", [])
    
    # Check if any scene has a low score (< 0.7)
    bad_scenes = [s for s in scenes if s.get("vision_qa_score", 1.0) < 0.7]
    
    # To prevent infinite loops, we track 'qa_retries' in state
    retries = state.get("validation_failures", 0)
    
    if bad_scenes and retries < 1:
        logger.warning("qa_router_loopback_triggered", job_id=job_id, bad_count=len(bad_scenes))
        state["validation_failures"] = retries + 1
        # Loop back to fix the motion (most common failure point)
        return "video_alchemist"
        
    logger.info("qa_router_passed", job_id=job_id)
    return "video_assembler"


async def final_persistence(state: UniversalGraphState) -> UniversalGraphState:
    """
    Final Checkpoint: Persists Agent 4 results (keyframes) and marks job as COMPLETED.
    """
    job_id = state.get("job_id")
    logger.info("final_persistence_reached", job_id=job_id)

    # Use high-performance asyncpg pool
    pool = await get_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                # 1. Bulk Update Scene Keyframes
                scenes = state.get("scenes", [])
                if scenes:
                    scene_data = [
                        (
                            s.get("keyframe_url"), 
                            s.get("audio_url"), 
                            s.get("lip_sync_video_url"), 
                            s.get("motion_video_url"),   
                            job_id, 
                            s.get("scene_number")
                        )
                        for s in scenes
                    ]
                    await conn.executemany(
                        """UPDATE scenes 
                           SET keyframe_url = $1, audio_url = $2, lip_sync_url = $3, motion_url = $4, pipeline_stage = 'CP2_RENDER' 
                           WHERE job_id = $5 AND scene_number = $6""",
                        scene_data
                    )

                # 2. Mark Job as COMPLETED
                video_url = state.get("video_url")
                await conn.execute(
                    "UPDATE jobs SET status = 'COMPLETED', pipeline_stage = 'CP2_RENDER', video_url = $1 WHERE id = $2",
                    video_url, job_id
                )
            logger.info("final_state_persisted_pool", job_id=job_id)
        except Exception as e:
            logger.error("final_persistence_pool_failed", job_id=job_id, error=str(e))
    else:
        # Supabase REST Fallback
        try:
            from backend.utils_auth import get_supabase_client
            supabase = get_supabase_client()
            
            # Update Scenes one by one (REST limitation)
            scenes = state.get("scenes", [])
            for s in scenes:
                supabase.table("scenes").update({
                    "keyframe_url": s.get("keyframe_url"),
                    "audio_url": s.get("audio_url"),
                    "lip_sync_url": s.get("lip_sync_video_url"),
                    "motion_url": s.get("motion_video_url"),
                    "pipeline_stage": "CP2_RENDER"
                }).eq("job_id", job_id).eq("scene_number", s.get("scene_number")).execute()
            
            # Update Job
            video_url = state.get("video_url")
            supabase.table("jobs").update({
                "status": "COMPLETED",
                "pipeline_stage": "CP2_RENDER",
                "video_url": video_url
            }).eq("id", job_id).execute()
            
            logger.info("final_state_persisted_rest", job_id=job_id)
        except Exception as e:
            logger.error("final_persistence_rest_failed", job_id=job_id, error=str(e))
    
    return state


# --- Compile the LangGraph Execution DAG ---
workflow = StateGraph(UniversalGraphState)

workflow.add_node("director", agent_director)
workflow.add_node("cinematographer", agent_cinematographer)
workflow.add_node("hook_analyst", agent_hook_analyst)
workflow.add_node("checkpoint_1", cp1_webhook)
async def hitl_approval_gate(state: UniversalGraphState) -> UniversalGraphState:
    """
    Agent 15: The HITL Approval Gate
    Strictly verifies that at least one scene has been APPROVED before moving to renders.
    """
    job_id = state.get("job_id")
    logger.info("hitl_gate_reached", job_id=job_id)
    
    # Update state to reflect we are waiting for approval if not already done
    state["pipeline_stage"] = "KEYFRAME_APPROVAL"
    state["current_agent"] = "HITL Gate"
    
    # Sync with DB to show 'WAITING_FOR_APPROVAL' in UI
    from backend.utils_sync import sync_pipeline_state
    await sync_pipeline_state(job_id, state, "HITL_PAUSE", status_message="Waiting for scene approval in Storyboard...")
    
    return state

def hitl_router(state: UniversalGraphState) -> str:
    """
    Conditional Edge: Checks if any scene is 'APPROVED' in the database.
    If yes, proceed to vocal_synthesizer.
    If no, loop back to the hitl_approval_gate (or exit if you prefer a hard stop).
    """
    # In a real-world scenario, we check the database here directly or via state
    # But since langgraph interrupts happen at node boundaries, 
    # if we are resumed, we check if we should move forward.
    from backend.utils_auth import get_supabase_client
    supabase = get_supabase_client()
    res = supabase.table("scenes").select("status").eq("job_id", state.get("job_id")).eq("status", "APPROVED").execute()
    
    if res.data and len(res.data) > 0:
        logger.info("hitl_gate_passed", job_id=state.get("job_id"), approved_count=len(res.data))
        return "vocal_synthesizer"
    
    # If the operator clicked the main UI button without selecting individual scenes,
    # we auto-approve all KEYFRAME_READY scenes to avoid an infinite recursion loop!
    logger.warning("hitl_gate_auto_approve_fallback", job_id=state.get("job_id"))
    try:
        updated = supabase.table("scenes").update({"status": "APPROVED"}).eq("job_id", state.get("job_id")).eq("status", "KEYFRAME_READY").execute()
        if updated.data and len(updated.data) > 0:
            logger.info("hitl_gate_passed", job_id=state.get("job_id"), auto_approved_count=len(updated.data))
            return "vocal_synthesizer"
    except Exception as e:
        logger.error("hitl_gate_auto_approve_failed", error=str(e))
        
    return "hitl_approval_gate" # Re-trigger the interrupt node ONLY if genuinely no scenes available


workflow.add_node("keyframe_architect", agent_keyframe_architect)
workflow.add_node("vocal_synthesizer", agent_vocal_synthesizer)
workflow.add_node("lip_sync", agent_lip_sync)
workflow.add_node("video_alchemist", agent_video_alchemist)
workflow.add_node("temporal_consistency", agent_temporal_consistency)
workflow.add_node("motion_interpolator", agent_motion_interpolator)
workflow.add_node("vision_qa", agent_vision_qa)
workflow.add_node("video_assembler", agent_video_assembler)
workflow.add_node("final_persistence", final_persistence)
workflow.add_node("motion_director", agent_motion_director)
workflow.add_node("hitl_approval_gate", hitl_approval_gate)

workflow.add_edge(START, "director")
workflow.add_edge("director", "cinematographer")
workflow.add_edge("cinematographer", "hook_analyst")

# Add the Conditional Router for the Hook Analyst loop hole
workflow.add_conditional_edges("hook_analyst", hook_router)

# Bridge CP1 directly to Motion Director then Agent 4
workflow.add_edge("checkpoint_1", "motion_director")
workflow.add_edge("motion_director", "keyframe_architect")

# CRITICAL: HITL GATE PROTECTION
workflow.add_edge("keyframe_architect", "hitl_approval_gate")
workflow.add_conditional_edges("hitl_approval_gate", hitl_router)

workflow.add_edge("vocal_synthesizer", "lip_sync")
workflow.add_edge("lip_sync", "video_alchemist")
workflow.add_edge("video_alchemist", "temporal_consistency")
workflow.add_edge("temporal_consistency", "motion_interpolator")
workflow.add_edge("motion_interpolator", "vision_qa")

# Quality Gate: Router decides if we assemble or re-shoot
workflow.add_conditional_edges("vision_qa", qa_router)

workflow.add_edge("video_assembler", "final_persistence")
workflow.add_edge("final_persistence", END)

# Physically inject checkpointer and hit the Native Pause
# We try to use SQLite for persistence, but fallback to Memory if it's missing.
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), "checkpoints.db")
    # Ensure absolute path for cross-process stability
    DB_PATH = os.path.abspath(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    memory = SqliteSaver(conn)
    logger.info("persistent_checkpointer_active", type="sqlite", path=DB_PATH)
except Exception as e:
    from langgraph.checkpoint.memory import MemorySaver
    memory = MemorySaver()
    logger.warning("volatile_checkpointer_active", type="memory", error=str(e))

agent_pipeline = workflow.compile(
    checkpointer=memory,
    interrupt_after=["checkpoint_1", "hitl_approval_gate"],
)
