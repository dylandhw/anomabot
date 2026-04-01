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



# docker log streaming
def stream_container_logs(container_name):
    client = docker.from_env()

    while True:
        try:
            container = client.containers.get(container_name)
            logger.info(f"Streaming logs from: {container_name}")

            for raw_line in container.logs(stream=True, follow=True, tail=30):
                line = raw_line.decode("utf-8", errors="replace").strip()

                timestamp = datetime.now().strftime("%H:%M:%S:")
                log_buffers[container_name].append(f"[{timestamp}] {line}")

        except docker.errors.NotFound:
            logger.warning(f"CONTAINER '{container_name}' NOT FOUND - RETRYING IN 15s")
            time.sleep(15)
        except Exception as e:
            logger.error(f"STREAM ERROR FOR '{container_name}': {e} - RETRYING IN 15S")
            time.sleep(15)

@tool
def report_anomaly(severity, container, description, fix):
    """
    Call this tool whenever you detect a real issue in the logs.
    Do **NOT** call if it if the logs appear to be healthy.

    Arguments:
        severity: One of the following: High, Medium, Low
        container: The name of the container where the issue was found
        description: A one-sentence summary of the issue
        fix: One concrete and reliable remediation action the operator should take.

    Returns:
        Confirmation string (used internally only)
    """
    anomalies_detected_total.inc()
    _print_alert(severity, container, description, fix)
    return f"ALERT RECORDE: [{severity}] {description}"
