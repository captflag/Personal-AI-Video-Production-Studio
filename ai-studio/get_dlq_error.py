import os
from dotenv import load_dotenv
from pathlib import Path
from supabase import create_client

env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

res = supabase.table("jobs").select("id, status, pipeline_stage, error_log").order("created_at", desc=True).limit(1).execute()
print("\n=== LATEST JOB STATUS ===")
if res.data:
    job = res.data[0]
    print(f"Job ID: {job['id']}")
    print(f"Status: {job['status']}")
    print(f"Stage: {job['pipeline_stage']}")
    print(f"Error Log: {job['error_log']}")
else:
    print("No jobs found.")
