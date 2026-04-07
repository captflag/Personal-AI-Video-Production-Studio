from backend.utils_auth import get_supabase_client
import uuid

s = get_supabase_client()
job_id = str(uuid.uuid4())
print(f"Testing Insert for ID: {job_id}")

try:
    res = s.table("jobs").insert({
        "id": job_id,
        "status": "INITIALIZING",
        "pipeline_stage": "TEST",
        "prompt": "Test Insert from Script",
        "updated_at": "2026-03-27T12:00:00Z"
    }).execute()
    print("Insert Success!")
except Exception as e:
    print(f"Insert Failed: {e}")
