"""
arq_settings.py
---------------
ARQ Redis connection pool settings.
Both the FastAPI gateway (for enqueuing) and the `arq` worker process
(for consuming) import this module so they share identical configuration.
"""
import os
from arq.connections import RedisSettings


# ARQ expects a RedisSettings object, not a raw URL string.
# We parse host/port out of the URL for maximum compatibility.
def get_redis_settings() -> RedisSettings:
    # Read at call time so .env has already been loaded by the time this runs.
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Strip scheme
    url = redis_url.replace("redis://", "").replace("rediss://", "")

    # Strip optional /db path (e.g. redis://localhost:6379/0 → localhost:6379)
    url = url.split("/")[0]

    parts = url.split(":")
    host = parts[0] or "localhost"
    port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 6379
    return RedisSettings(host=host, port=port)
