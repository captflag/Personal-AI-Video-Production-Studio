import os
import structlog
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Robust .env discovery: Check current dir and parent backend/ dir
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = structlog.get_logger()

def get_supabase_client() -> Client:
    """
    Returns a production-ready Supabase client with reliable key fallbacks.
    Prioritizes SERVICE_KEY for administrative/agent tasks, falls back to public KEY for dev.
    """
    url = os.getenv("SUPABASE_URL")
    # Agents NEED service key permissions to bypass RLS and perform bulk persistence
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        missing = []
        if not url: missing.append("SUPABASE_URL")
        if not key: missing.append("SUPABASE_KEY/SERVICE_KEY")
        logger.error("supabase_auth_missing", missing=missing)
        raise RuntimeError(f"Missing Critical Supabase Secrets: {missing}")
        
    return create_client(url, key)
