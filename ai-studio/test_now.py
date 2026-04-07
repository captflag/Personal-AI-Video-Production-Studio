import os
import time
from dotenv import load_dotenv
from pathlib import Path
from supabase import create_client

env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

try:
    print("Testing now()")
    res = supabase.table("jobs").update({
        "updated_at": "now()"
    }).eq("id", "9274804d-e9b8-4b18-a263-ea4b3a404a29").execute()
    print("now() success:", res.data)
except Exception as e:
    print("now() FAILED:", e)

try:
    print("Testing isoformat()")
    from datetime import datetime, timezone
    res = supabase.table("jobs").update({
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", "9274804d-e9b8-4b18-a263-ea4b3a404a29").execute()
    print("isoformat() success:", res.data)
except Exception as e:
    print("isoformat() FAILED:", e)
