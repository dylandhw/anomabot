import asyncio
import logging
import random
import time
from fastapi import FastAPI
from fastapi.routing import asynccontextmanager

logger = logging.getLogger("uvicorn")


# test logs for while i build this
ERRORS = [
    "Database connection timeout after 30s",
    "Unhandled exception in request handler: NullPointerException",
    "Failed to acquire lock on resource /tmp/app.lock",
    "Memory usage exceeded 90% threshold",
]

WARNINGS = [
    "Response time exceeded 500ms SLA",
    "Retry attempt 2/3 for upstream service",
    "Cache miss rate above 40% in last 60ms",
]

INFO = [
    "GET /health 200 12ms",
    "GET /api/users 200 45ms",
    "POST /api/orders 201 120ms",
    "Background job completed: cleanup_sessions",
]


# generate some test logs
async def log_gen():
    while True:
        chance = random.random()
        if chance < 0.05:
            logger.error(random.choice(ERRORS))
        elif chance < 0.20:
            logger.warning(random.choice(WARNINGS))
        else:
            logger.info(random.choice(INFO))
        await asyncio.sleep(random.uniform(2, 5))

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("app starting up")
    asyncio.create_task(log_gen())
    yield
    print("app shutting down")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}
