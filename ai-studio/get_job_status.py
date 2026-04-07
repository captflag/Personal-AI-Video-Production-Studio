import os
import asyncio
import structlog
from dotenv import load_dotenv
from backend.utils_auth import get_supabase_client

load_dotenv()
logger = structlog.get_logger()

async def get_status():
    try:
        s = get_supabase_client()
        res = s.table("jobs").select("*").order("created_at", descending=True).limit(1).execute()
        if res.data:
            job = res.data[0]
            print(f"JOB_ID: {job['id']}")
            print(f"STATUS: {job['status']}")
            print(f"STAGE: {job['pipeline_stage']}")
            print(f"UPDATED: {job['updated_at']}")
            if job.get('last_error'):
                print(f"ERROR: {job['last_error']}")
        else:
            print("NO_JOBS_FOUND")
    except Exception as e:
        print(f"QUERY_FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(get_status())
