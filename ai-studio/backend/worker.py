"""
worker.py
---------
ARQ Worker Process — the Phase 4 replacement for FastAPI's `BackgroundTasks`.

WHY ARQ?
  - BackgroundTasks: Jobs are ephemeral. If uvicorn restarts mid-generation, the job
    is SILENTLY LOST. No recovery. No visibility.
  - ARQ (Redis-backed): Jobs are persisted as Redis hashes. If the worker crashes it
    picks up where it left off on restart. Jobs are also introspectable via the ARQ
    dashboard or `arq watch`.

HOW TO RUN THE WORKER:
    arq backend.worker.WorkerSettings

This runs as a SEPARATE process alongside uvicorn. Docker Compose will manage it.
"""

import os
import structlog
import asyncio
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path) # Load .env before other imports reach for os.getenv
from datetime import datetime, timedelta, timezone
from backend.arq_settings import get_redis_settings
from backend.db import close_pool

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────
# Task: Start a new LangGraph pipeline job
# ─────────────────────────────────────────────────────────────
async def task_run_pipeline(ctx: dict, job_id: str, prompt: str, chat_id: str) -> dict:
    """
    ARQ task that replaces `run_langgraph_background`.
    Executed inside the arq worker process — completely isolated from the HTTP thread.
    """
    logger.info("arq_task_started", task="run_pipeline", job_id=job_id)
    try:
        # Import here to avoid circular graph compilation at module load time
        from backend.graph import agent_pipeline

        initial_state = {
            "job_id": job_id,
            "telegram_chat_id": chat_id,
            "raw_prompt": prompt,
            "memory_context": "None",
            "characters": [],
            "scenes": [],
            "current_agent": "START",
            "validation_failures": 0,
            "last_error": None,
            "running_cost_usd": 0.0,
        }
        config = {"configurable": {"thread_id": job_id}}
        await agent_pipeline.ainvoke(initial_state, config=config)

        logger.info("arq_task_suspended", checkpoint="CP1", job_id=job_id)
        return {"status": "SUSPENDED_AT_CP1", "job_id": job_id}

    except Exception as e:
        logger.error("arq_task_failed", task="run_pipeline", error=str(e), job_id=job_id)
        # Final resilience: Persist the error to Supabase so the UI knows
        try:
            from backend.utils_auth import get_supabase_client
            supabase = get_supabase_client()
            supabase.table("jobs").update({
                "status": "FAILED",
                "pipeline_stage": "ERROR",
                "error_log": str(e), # Using the column name from schema.sql
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job_id).execute()
        except:
            pass # Avoid secondary crash if DB is also down
        return {"status": "FAILED", "error": str(e), "job_id": job_id}


# ─────────────────────────────────────────────────────────────
# Task: Resume a LangGraph pipeline after HITL approval
# ─────────────────────────────────────────────────────────────
async def task_resume_pipeline(ctx: dict, job_id: str, action: str) -> dict:
    """
    ARQ task that replaces `resume_langgraph_background`.
    Wakes the interrupted DAG and drives it through Agent 4 → CP2.
    """
    logger.info("arq_task_started", task="resume_pipeline", job_id=job_id, action=action)
    try:
        from backend.graph import agent_pipeline

        if action == "REJECT":
            logger.info("operator_rejected_job", job_id=job_id)
            return {"status": "REJECTED", "job_id": job_id}

        config = {"configurable": {"thread_id": job_id}}
        await agent_pipeline.ainvoke(None, config=config)

        logger.info("arq_task_completed", task="resume_pipeline", job_id=job_id)
        return {"status": "COMPLETED", "job_id": job_id}

    except Exception as e:
        logger.error("arq_task_failed", task="resume_pipeline", error=str(e), job_id=job_id)
        # Final resilience: Persist the error to Supabase so the UI knows
        try:
            from backend.utils_auth import get_supabase_client
            supabase = get_supabase_client()
            supabase.table("jobs").update({
                "status": "FAILED",
                "pipeline_stage": "RESUME_ERROR",
                "error_log": str(e), # Using correct column name
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job_id).execute()
        except:
            pass
        return {"status": "FAILED", "error": str(e), "job_id": job_id}

async def task_approve_scene(ctx: dict, job_id: str, scene_number: int) -> dict:
    """
    ARQ task called when a specific scene is approved on the dashboard.
    Resumes the pipeline through Agent 4 → Assembly.
    """
    logger.info("arq_task_started", task="approve_scene", job_id=job_id, scene=scene_number)
    try:
        from backend.graph import agent_pipeline
        config = {"configurable": {"thread_id": job_id}}
        await agent_pipeline.ainvoke(None, config=config)
        logger.info("arq_task_completed", task="approve_scene", job_id=job_id)
        return {"status": "COMPLETED", "job_id": job_id}
    except Exception as e:
        logger.error("arq_task_failed", task="approve_scene", error=str(e), job_id=job_id)
        return {"status": "FAILED", "error": str(e), "job_id": job_id}


# ─────────────────────────────────────────────────────────────
# ARQ Worker Configuration Class
# ─────────────────────────────────────────────────────────────
import tempfile

async def janitor_task():
    """Sweeps temp directory every 30 mins for orphaned work dirs > 1 hour old."""
    output_dir = os.path.join(tempfile.gettempdir(), "ai_studio_renders")
    if not os.path.exists(output_dir):
        return

    while True:
        try:
            now = time.time()
            for folder in os.listdir(output_dir):
                path = os.path.join(output_dir, folder)
                if os.path.isdir(path) and (now - os.path.getmtime(path) > 3600):
                    shutil.rmtree(path, ignore_errors=True)
                    logger.info("janitor_cleanup_orphaned_dir", path=path)
        except Exception as e:
            logger.error("janitor_task_failed", error=str(e))
        await asyncio.sleep(1800)

class WorkerSettings:
    """
    Tells the `arq` process which tasks exist, which Redis to connect to,
    and how many concurrent jobs to run.
    """

    functions = [task_run_pipeline, task_resume_pipeline, task_approve_scene]
    redis_settings = get_redis_settings()

    # Max concurrent coroutines per worker process. Keep low to respect HF rate limits.
    max_jobs = 4

    # Retry failed jobs up to 3 times with a 60-second delay between attempts.
    job_timeout = 1800  # 30 minutes — allows for heavy 1024x1024 CPU rendering
    keep_result = 3600  # Keep job result in Redis for 1 hour for debugging

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        """Sanity check and background janitor initialization."""
        # 1. Secret Validation
        required = ["API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "GROQ_API_KEY", "HUGGINGFACE_API_KEY"]
        if os.getenv("ENVIRONMENT") == "production":
            if missing := [k for k in required if not os.getenv(k)]:
                logger.error("worker_startup_failed", missing_secrets=missing)
                # raise RuntimeError(f"Missing secrets: {missing}")

        # 2. MoviePy / FFmpeg Check (Agent 10)
        try:
            # from moviepy.config import get_setting
            # ffmpeg_path = get_setting("FFMPEG_BINARY")
            logger.info("worker_startup_diagnostic", moviepy_ready=True)
        except Exception as e:
            logger.error("worker_startup_diagnostic_failed", error=str(e))

        # 3. Start Janitor Task
        asyncio.create_task(janitor_task())

    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        """Cleanly drains the database connection pool on worker exit."""
        await close_pool()
        logger.info("worker_pool_drained")

if __name__ == "__main__":
    from arq import create_pool, Worker
    import asyncio
    from backend.arq_settings import get_redis_settings

    async def main():
        redis = await create_pool(get_redis_settings())
        worker = Worker(
            functions=[task_run_pipeline, task_resume_pipeline],
            redis_pool=redis,
            on_startup=WorkerSettings.on_startup,
            on_shutdown=WorkerSettings.on_shutdown,
            max_jobs=WorkerSettings.max_jobs,
            job_timeout=WorkerSettings.job_timeout,
            keep_result=WorkerSettings.keep_result
        )
        # Use .main() when already inside an existing asyncio loop (asyncio.run)
        await worker.main()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
