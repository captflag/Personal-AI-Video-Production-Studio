import os
import asyncio
import requests
import structlog
from dotenv import load_dotenv
from backend.utils_auth import get_supabase_client
from backend.db import get_pool
from backend.arq_settings import get_redis_settings
from arq.connections import create_pool

load_dotenv()
logger = structlog.get_logger()

async def check_supabase():
    try:
        s = get_supabase_client()
        buckets = s.storage.list_buckets()
        logger.info("health_check_supabase", status="OK", buckets=[b.name for b in buckets])
        return True
    except Exception as e:
        logger.error("health_check_supabase", status="FAILED", error=str(e))
        return False

async def check_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("health_check_groq", status="MISSING_KEY")
        return False
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        # Use the modern Llama 3.1 8B Instant model
        payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "hi"}]}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            logger.info("health_check_groq", status="OK")
            return True
        else:
            logger.error("health_check_groq", status="FAILED", code=res.status_code, body=res.text[:100])
            return False
    except Exception as e:
        logger.error("health_check_groq", status="ERROR", error=str(e))
        return False

async def check_nvidia_nim():
    api_key = os.getenv("NVIDIA_NIM_KEY")
    if not api_key:
        logger.warning("health_check_nvidia_nim", status="MISSING_KEY")
        return False
    try:
        # Use the correct SDXL endpoint
        # Use the modern Stable Diffusion XL endpoint
        url = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        # We use a POST with a tiny prompt to verify the key. 
        # Ge=5 is required by the NIM validator.
        payload = {"text_prompts": [{"text": "a", "weight": 1}], "steps": 5} 
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            logger.info("health_check_nvidia_nim", status="OK")
            return True
        else:
            logger.error("health_check_nvidia_nim", status="FAILED", code=res.status_code, body=res.text[:100])
            return False
    except Exception as e:
        logger.error("health_check_nvidia_nim", status="ERROR", error=str(e))
        return False

async def check_huggingface():
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        logger.warning("health_check_huggingface", status="MISSING_KEY")
        return False
    try:
        # Migrate to the new HuggingFace Router (2025 Standard)
        url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
        headers = {"Authorization": f"Bearer {api_key}"}
        # Model status check via POST (dry run with empty input usually works or gives a model-specific error)
        res = requests.post(url, headers=headers, json={"inputs": "a"}, timeout=10)
        if res.status_code in [200, 503]:
            logger.info("health_check_huggingface", status="OK")
            return True
        else:
            logger.error("health_check_huggingface", status="FAILED", code=res.status_code, body=res.text[:100])
            return False
    except Exception as e:
        logger.error("health_check_huggingface", status="ERROR", error=str(e))
        return False

async def check_redis():
    try:
        pool = await create_pool(get_redis_settings())
        await pool.close()
        logger.info("health_check_redis", status="OK")
        return True
    except Exception as e:
        logger.error("health_check_redis", status="FAILED", error=str(e))
        return False

async def check_cinematic_standards():
    """Verifies 24fps and 8Mbps constants are active."""
    try:
        from backend.agents.video_assembler import agent_video_assembler
        # Validation by file inspection (simulated via logic check)
        import inspect
        source = inspect.getsource(agent_video_assembler)
        if 'fps=24' in source and 'bitrate="8000k"' in source:
            logger.info("health_check_cinematic_standards", status="OK", layers=["24fps", "8Mbps"])
            return True
        else:
            logger.warning("health_check_cinematic_standards", status="MISSING_CONSTANTS")
            return False
    except Exception as e:
        logger.error("health_check_cinematic_standards", status="ERROR", error=str(e))
        return False

async def check_telemetry_hardening():
    """Verifies State Heartbeats are injected into core agents."""
    agents = ["director", "cinematographer", "keyframe_architect", "vocal_synthesizer", "vision_qa", "video_alchemist", "video_assembler"]
    missing = []
    try:
        for agent in agents:
            with open(f"backend/agents/{agent}.py", "r") as f:
                if "sync_pipeline_state" not in f.read():
                    missing.append(agent)
        
        if not missing:
            logger.info("health_check_telemetry", status="OK", heartbeats="Full Coverage")
            return True
        else:
            logger.warning("health_check_telemetry", status="FAIL", missing=missing)
            return False
    except Exception as e:
        logger.error("health_check_telemetry", status="ERROR", error=str(e))
        return False

async def check_neural_qa_gate():
    """Verifies Agent 5 is correctly registered in the DAG."""
    try:
        from backend.graph import workflow
        if "vision_qa" in workflow.nodes:
            logger.info("health_check_neural_qa", status="OK", gate="Armored")
            return True
        else:
            logger.warning("health_check_neural_qa", status="MISSING_NODE")
            return False
    except Exception as e:
        logger.error("health_check_neural_qa_failed", error=str(e))
        return False

async def run_diagnostics():
    logger.info("studio_master_health_check_ignited")
    results = await asyncio.gather(
        check_supabase(),             # Phase 1
        check_groq(),                 # Phase 2
        check_nvidia_nim(),           # Phase 3
        check_huggingface(),          # Phase 4
        check_redis(),                # Phase 5
        check_cinematic_standards(),  # Phase 6
        check_telemetry_hardening(),  # Phase 7
        check_persistence_sync(),     # Phase 8: REST Fallback
        check_neural_qa_gate()        # Phase 9: Neural QA Gate
    )
    
    score = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\n[Hardening Audit] Neural Fidelity & Orchestration...")
    print(f"STATUS: {'FLIGHT_READY' if score == total else 'MAINTENANCE_REQUIRED'}")
    print(f"HEALTH SCORE: {score}/{total}")
    
    logger.info("studio_health_audit_complete", score=f"{score}/{total}")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
