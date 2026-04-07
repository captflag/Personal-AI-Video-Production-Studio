import structlog
from backend.utils_auth import get_supabase_client

logger = structlog.get_logger()

async def sync_pipeline_state(job_id: str, state: dict, stage: str = None, status_message: str = None):
    """
    Precision Sync: Persists granular agent telemetry to Supabase.
    """
    try:
        supabase = get_supabase_client()
        
        # 1. Update Job Status & Stage
        update_data = {
            "updated_at": "now()",
        }
        if stage:
            # We combine stage and message for max visibility in legacy UI fields
            display_stage = f"{stage}: {status_message}" if status_message else stage
            update_data["pipeline_stage"] = display_stage
            
        supabase.table("jobs").update(update_data).eq("id", job_id).execute()
        
        # 2. Bulk Update Scenes
        scenes = state.get("scenes", [])
        for scene in scenes:
            scene_num = scene.get("scene_number")
            
            # Determine logic-driven status
            current_status = scene.get("status", "PENDING")
            
            # If we have a motion URL, it's definitely COMPLETED
            if scene.get("motion_video_url"):
                new_status = "COMPLETED"
            # If it was already APPROVED or is currently PROCESSING, don't revert to PENDING
            elif current_status in ["APPROVED", "PROCESSING"]:
                new_status = current_status
            # If keyframe is ready but not yet approved for video
            elif scene.get("keyframe_url"):
                new_status = "KEYFRAME_READY"
            else:
                new_status = "PENDING"
                
            scene_update = {
                "keyframe_url": scene.get("keyframe_url"),
                "audio_url": scene.get("audio_url"),
                "lip_sync_url": scene.get("lip_sync_video_url"),
                "motion_url": scene.get("motion_video_url"),
                "status": new_status,
                "updated_at": "now()"
            }
            scene_update = {k: v for k, v in scene_update.items() if v is not None}
            if scene_update:
                supabase.table("scenes").update(scene_update).eq("job_id", job_id).eq("scene_number", scene_num).execute()
                
        logger.info("pipeline_precision_synced", job_id=job_id, stage=stage, msg=status_message)
        
    except Exception as e:
        logger.warning("pipeline_heartbeat_failed", job_id=job_id, error=str(e))
