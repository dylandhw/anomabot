import os
import time
import threading
import logging
from collections import deque, defaultdict
from datetime import datetime

import docker
from prometheus_client import Counter, start_http_server
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENT] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# prometheus metrics
logs_processed_total = Counter(
    "logs_processed_total",
    "total log lines ingested from all containters",
)
anomalies_detected_total = Counter(
    "anomalies_detected_total",
    "total anomalies detected by the agent",
)

# feedback loop reads from deque, streamer writes to them (per container)
LOG_BUFFER_SIZE = 60
log_buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=LOG_BUFFER_SIZE))
