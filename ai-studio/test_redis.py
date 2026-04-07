import redis
import os
from dotenv import load_dotenv

load_dotenv("backend/.env")
url = os.getenv("REDIS_URL", "redis://localhost:6379")
print(f"Connecting to: {url}")

r = redis.from_url(url)
keys = r.keys("arq:*")
print(f"ARQ Keys found: {len(keys)}")
for k in keys:
    print(f" - {k.decode()}")

# Check the queue
queued = r.zrange("arq:queue", 0, -1)
print(f"Jobs in arq:queue: {len(queued)}")
for q in queued:
    print(f" - Queued ID: {q.decode()}")
