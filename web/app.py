import asyncio
import logging
import random
import time
from fastapi import FastAPI

app = FastAPI()
logger = logging.getLogger("uvicorn")


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
