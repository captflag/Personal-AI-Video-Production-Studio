import redis
import os
import pickle
from dotenv import load_dotenv

load_dotenv("backend/.env")
url = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(url)

res_key = "arq:result:ad522d211c5f4dc2933a7eb65f4b7d40"
data = r.get(res_key)
if data:
    # ARQ results are msgpack or pickle? arq uses msgpack by default
    # But let's just see the raw bytes or try to decode
    import msgpack
    try:
        decoded = msgpack.unpackb(data)
        print(f"Result for {res_key}: {decoded}")
    except Exception as e:
         print(f"Msgpack fail: {e}")
         print(f"Raw: {data[:100]}")
else:
    print(f"No result found for {res_key}")
