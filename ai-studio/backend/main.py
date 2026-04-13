import os
from pathlib import Path
from dotenv import load_dotenv

# Inherently load physical keys before any Graph compilation
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
import uuid
import asyncio
import structlog
from datetime import datetime, timedelta, timezone

logger = structlog.get_logger()

# --- Rate Limiting ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- ARQ Queue Client ---
from arq.connections import create_pool
from backend.arq_settings import get_redis_settings

# --- Database Pool ---
from backend.db import get_pool, close_pool

# ─────────────────────────────────────────────────────────────
# Secrets & Auth
# ─────────────────────────────────────────────────────────────
API_KEY = os.getenv("API_KEY")

REQUIRED_SECRETS = ["API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "GROQ_API_KEY", "HUGGINGFACE_API_KEY", "ELEVENLABS_API_KEY"]
if os.getenv("ENVIRONMENT") == "production":
    if missing := [k for k in REQUIRED_SECRETS if not os.getenv(k)]:
        raise RuntimeError(f"🔥 FATAL: Missing Critical Secrets for Production: {missing}")

API_KEY = API_KEY or "dev-secret-key-123"

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

# ─────────────────────────────────────────────────────────────
# Rate Limiter
# ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="AI Video Studio — Universal Gateway", version="2.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─────────────────────────────────────────────────────────────
# Phase 4: DLQ Sweeper — now handles HITL TTL (24h) too
# ─────────────────────────────────────────────────────────────
async def dlq_sweeper_task():
    """
    Sweeps every 5 minutes:
    1. Jobs stuck in PROCESSING > 15 min → FAILED_DLQ
    2. Jobs stuck in HITL_PAUSE > 24 hours → FAILED_TTL (operator never responded)
    """
    logger.info("dlq_sweeper_initialized", interval_minutes=5)
    while True:
        try:
            from backend.utils_auth import get_supabase_client
            supabase = get_supabase_client()

            # Compute cutoff timestamps in Python
            now = datetime.now(timezone.utc)
            dlq_cutoff = (now - timedelta(minutes=120)).isoformat()
            ttl_cutoff = (now - timedelta(hours=24)).isoformat()

            # 1. Mark stuck PROCESSING jobs as failed (>120 min)
            result = (
                supabase.table("jobs")
                .update({"status": "FAILED_DLQ", "pipeline_stage": "DLQ_ERROR"})
                .eq("status", "PROCESSING")
                .lt("updated_at", dlq_cutoff)
                .execute()
            )
            failed_dlq = len(result.data) if result.data else 0
            if failed_dlq:
                logger.warning("dlq_jobs_swept", count=failed_dlq, reason="stuck_in_processing")

            # 2. Mark expired HITL_PAUSE jobs as TTL-failed (>24 hours)
            result_ttl = (
                supabase.table("jobs")
                .update({"status": "FAILED_TTL", "pipeline_stage": "HITL_TIMEOUT"})
                .eq("status", "HITL_PAUSE")
                .lt("updated_at", ttl_cutoff)
                .execute()
            )
            failed_ttl = len(result_ttl.data) if result_ttl.data else 0
            if failed_ttl:
                logger.warning("hitl_ttl_jobs_swept", count=failed_ttl, reason="operator_24h_timeout")

        except Exception as e:
            logger.error("dlq_sweeper_exception", error=str(e))
        await asyncio.sleep(300)


# ─────────────────────────────────────────────────────────────
# Helper: Ensure Supabase Buckets Exist
# ─────────────────────────────────────────────────────────────
async def ensure_buckets_exist():
    from backend.utils_auth import get_supabase_client
    supabase = get_supabase_client()
    required = ["keyframes", "audio", "videos"]
    for b in required:
        try:
            # Simple check/create logic
            supabase.storage.create_bucket(b, options={"public": True})
            logger.info("bucket_verified_or_created", name=b)
        except Exception:
            # Usually fails if already exists, which is fine
            pass

# ─────────────────────────────────────────────────────────────
# FastAPI Lifecycle
# ─────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    # ARQ queue pool — used to enqueue background jobs (Optional in Zero-GPU mode)
    try:
        # Reduced timeout to prevent startup hangs when Redis is offline
        app.state.arq_pool = await asyncio.wait_for(create_pool(get_redis_settings()), timeout=2.0)
        logger.info("arq_pool_ready")
    except Exception as e:
        logger.warning("arq_pool_unavailable", error="Redis Offline", fallback="BackgroundTasks enabled")
        app.state.arq_pool = None

    # asyncpg DB pool
    app.state.db_pool = await get_pool()

    # Buckets verification
    await ensure_buckets_exist()

    # DLQ sweeper
    asyncio.create_task(dlq_sweeper_task())


@app.on_event("shutdown")
async def shutdown_event():
    # 1. Close DB Pool
    await close_pool()
    
    # 2. Close ARQ Pool
    if arq_pool := getattr(app.state, "arq_pool", None):
        await arq_pool.close()
        logger.info("arq_pool_closed")
        
    logger.info("shutdown_complete")


# ─────────────────────────────────────────────────────────────
# Middlewares
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Guarantees n8n never receives a raw HTML 500 stack trace."""
    logger.error("unhandled_gateway_exception", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "stage": "FASTAPI_GATEWAY_CRASH"},
    )


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────
class StartJobRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    raw_prompt: str = Field(..., min_length=10, max_length=2000, description="The user's scene description")
    chat_id: str = Field(..., min_length=1, max_length=50, description="Telegram chat ID")
    character_design: Optional[str] = Field(None, max_length=1000, description="The blueprint for the main character")
    character_name: Optional[str] = Field(None, max_length=100, description="Explicit character name to enforce")
    character_reference_url: Optional[str] = Field(None, max_length=2000, description="URL to character image for Face Locking (PuLID/InstantID)")


class ResumeJobRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    action: str = Field(..., pattern="^(APPROVE|REJECT|REGENERATE|APPROVE_RESUME)$", description="Operator action")


# ─────────────────────────────────────────────────────────────
# Helper: Dispatch a task to ARQ, falling back to BackgroundTasks
# ─────────────────────────────────────────────────────────────
async def _enqueue_or_fallback(request: Request, task_name: str, background_tasks, fallback_fn, **kwargs):
    """
    Directly uses in-process BackgroundTasks to bypass the standalone worker requirement.
    This was the successful 'previous technique' used during Phase 3.
    """
    background_tasks.add_task(fallback_fn, **kwargs)
    logger.info("job_enqueued_background_tasks", task=task_name, **kwargs)
    return "BackgroundTasks"


# ─────────────────────────────────────────────────────────────
# Async fallback functions (used when Redis is offline)
# ─────────────────────────────────────────────────────────────
async def _fallback_run_pipeline(
    job_id: str, prompt: str, chat_id: str, 
    character_design: Optional[str] = None,
    character_name: Optional[str] = None,
    character_reference_url: Optional[str] = None
):
    logger.info("fallback_worker_started", job_id=job_id)
    try:
        from backend.graph import agent_pipeline
        characters = []
        if character_design or character_name or character_reference_url:
            c_name = character_name or "Main Hero"
            c_desc = character_design or f"Hyper-realistic cinematic depiction of {c_name}"
            characters.append({
                "id": "hero",
                "name": c_name,
                "physical_description": c_desc,
                "outfit": "Default cinematic outfit",
                "locked_face_url": character_reference_url,
                "voice_id": None
            })

        initial_state = {
            "job_id": job_id, "telegram_chat_id": chat_id, "raw_prompt": prompt,
            "memory_context": "None", "characters": characters, "scenes": [],
            "current_agent": "START", "validation_failures": 0,
            "last_error": None, "running_cost_usd": 0.0,
        }
        config = {"configurable": {"thread_id": job_id}}
        await agent_pipeline.ainvoke(initial_state, config=config)
        logger.info("fallback_worker_suspended", checkpoint="CP1", job_id=job_id)
    except Exception as e:
        logger.error("fallback_worker_crashed", error=str(e), job_id=job_id)


async def _fallback_resume_pipeline(job_id: str, action: str):
    from backend.graph import agent_pipeline
    config = {"configurable": {"thread_id": job_id}}
    if action == "REJECT":
        logger.info("operator_rejected_job", job_id=job_id)
        return
    try:
        # If action is APPROVE_SCENE, we don't need special handling here yet 
        # as the video_alchemist checks the database/state status.
        await agent_pipeline.ainvoke(None, config=config)
        logger.info("fallback_resume_completed", job_id=job_id)
    except Exception as e:
        logger.error("fallback_resume_crashed", error=str(e), job_id=job_id)

async def _fallback_approve_scene(job_id: str, scene_number: int):
    """
    Specifically resumes the pipeline after a scene approval.
    """
    from backend.graph import agent_pipeline
    config = {"configurable": {"thread_id": job_id}}
    try:
        # 1. Fetch current state to ensure we are modifying the latest snapshot
        current_state = await agent_pipeline.aget_state(config)
        if not current_state.values:
            logger.error("scene_approval_missing_state", job_id=job_id)
            return

        scenes = list(current_state.values.get("scenes", []))
        updated = False
        for scene in scenes:
            if scene.get("scene_number") == scene_number:
                scene["status"] = "APPROVED"
                updated = True
        
        if not updated:
            logger.warning("scene_approval_number_not_found", job_id=job_id, scene=scene_number)
            return

        # 2. PHYSICALLY update the checkpointer state before ainvoke
        # This is CRITICAL for LangGraph to see the change after an interrupt
        await agent_pipeline.aupdate_state(config, {"scenes": scenes})
        
        # 3. Resume the thread
        await agent_pipeline.ainvoke(None, config=config)
        logger.info("scene_approval_checkpoint_updated_and_resumed", job_id=job_id, scene=scene_number)
    except Exception as e:
        logger.error("scene_approval_resume_failed", error=str(e), job_id=job_id)


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@app.post("/jobs/start", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def start_pipeline(req: StartJobRequest, request: Request, background_tasks: BackgroundTasks):
    """
    Initializes a new video generation job and dispatches it to ARQ
    (or BackgroundTasks if Redis is offline).
    """
    job_id = str(uuid.uuid4())
    logger.info("job_start_received", job_id=job_id, prompt_length=len(req.raw_prompt))

    # 1. Persist Initial Job State to Supabase (Mandatory for UI visibility)
    from backend.utils_auth import get_supabase_client
    try:
        supabase = get_supabase_client()
        supabase.table("jobs").insert({
            "id": job_id,
            "status": "INITIALIZING",
            "pipeline_stage": "SCRIPT",
            "prompt": req.raw_prompt,
            "character_design": req.character_design, # Track character blueprint in DB
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        logger.info("job_persisted_supabase", job_id=job_id)
    except Exception as e:
        logger.error("job_persist_failed", error=str(e), job_id=job_id)
        # THROW ERROR: Do not start the job if we can't track it!
        raise HTTPException(status_code=500, detail=f"Database Persistence Failure: {str(e)}")

    queue_type = await _enqueue_or_fallback(
        request,
        task_name="task_run_pipeline",
        background_tasks=background_tasks,
        fallback_fn=_fallback_run_pipeline,
        job_id=job_id,
        prompt=req.raw_prompt,
        chat_id=req.chat_id,
        character_design=req.character_design,
        character_name=req.character_name,
        character_reference_url=req.character_reference_url,
    )

    return {
        "status": "INITIALIZING",
        "job_id": job_id,
        "queue": queue_type,
        "message": "LangGraph pipeline dispatched.",
    }


@app.post("/jobs/{job_id}/resume", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def resume_pipeline(job_id: str, request: Request, background_tasks: BackgroundTasks, req: Optional[ResumeJobRequest] = None):
    """
    Called by n8n or Dashboard after an operator action.
    """
    action = req.action if req else "APPROVE"
    logger.info("job_resume_received", job_id=job_id, action=action)

    # --- Instant Dashboard Sync ---
    try:
        from backend.utils_auth import get_supabase_client
        supabase = get_supabase_client()
        supabase.table("jobs").update({
            "status": "PROCESSING",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", job_id).execute()
        logger.info("job_status_flipped_processing", job_id=job_id)
    except Exception as e:
        logger.warning("job_status_flip_failed", error=str(e))

    queue_type = await _enqueue_or_fallback(
        request,
        task_name="task_resume_pipeline",
        background_tasks=background_tasks,
        fallback_fn=_fallback_resume_pipeline,
        job_id=job_id,
        action=action, # Use the computed action
    )

    return {
        "status": "RESUMING",
        "job_id": job_id,
        "action_received": req.action,
        "queue": queue_type,
        "message": "Pipeline resuming into Agent 4.",
    }


@app.post("/jobs/{job_id}/scenes/{scene_number}/approve", dependencies=[Depends(verify_api_key)])
async def approve_scene(job_id: str, scene_number: int, request: Request, background_tasks: BackgroundTasks):
    """
    Promotes a specific keyframe to video production.
    """
    logger.info("scene_approval_received", job_id=job_id, scene=scene_number)

    # 1. Update Scene Status in Supabase
    from backend.utils_auth import get_supabase_client
    try:
        supabase = get_supabase_client()
        supabase.table("scenes").update({"status": "APPROVED"}).eq("job_id", job_id).eq("scene_number", scene_number).execute()
        
        # 2. Check if Job is paused and needs a nudge
        job_res = supabase.table("jobs").select("status").eq("id", job_id).single().execute()
        job_status = job_res.data.get("status")

        # Note: We NO LONGER auto-resume here. 
        # The user will click the 'APPROVE & START RENDERS' button on the dashboard
        # to trigger the full assembly once they've chosen all scenes.
        
        return {"status": "APPROVED", "message": f"Scene {scene_number} marked for production."}
    except Exception as e:
        logger.error("scene_approval_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Returns the current status, pipeline stage, and results (keyframes/video)
    for a specific job. Handles race conditions where job might not be persisted yet.
    """
    from backend.utils_auth import get_supabase_client
    from postgrest.exceptions import APIError
    
    supabase = get_supabase_client()
    
    try:
        # 1. Fetch Job
        job_res = supabase.table("jobs").select("*").eq("id", job_id).single().execute()
        
        # 2. Fetch Scenes
        scenes_res = supabase.table("scenes").select("*").eq("job_id", job_id).order("scene_number").execute()
        
        return {
            "id": job_id,
            "status": job_res.data.get("status"),
            "pipeline_stage": job_res.data.get("pipeline_stage"),
            "video_url": job_res.data.get("video_url"),
            "error_log": job_res.data.get("error_log"), # Crucial for 'piplines errors' visibility
            "scenes": scenes_res.data or [],
            "updated_at": job_res.data.get("updated_at")
        }
    except APIError as e:
        # Log the error but return 404/202 to avoid crashing the frontend
        logger.warning("job_status_db_error", job_id=job_id, error=str(e))
        return {
            "id": job_id,
            "status": "INITIALIZING",
            "pipeline_stage": "QUEUED",
            "video_url": None,
            "scenes": [],
            "updated_at": None
        }
    except Exception as e:
        logger.error("job_status_unhandled_error", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error during status fetch")


@app.get("/health")
def health_check():
    """Heart-beat check for Docker and n8n verifications."""
    arq_ok = getattr(app.state, "arq_pool", None) is not None
    return {"status": "ok", "service": "AI Studio Backend v2", "arq_queue": arq_ok}


# ─────────────────────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
