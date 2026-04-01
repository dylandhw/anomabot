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
def get_recent_logs(container_name):
    """
    Return the most recetn buffered log lines for a given Docker container.
    Use this to fetch logs before analyzing them.

    Args:
        A newline-string of recent log lines, or a message if empty.
    """

    buffer = log_buffers.get(container_name)
    if not buffer:
        return f"NO LOGS BUFFERED YET FOR CONTAINER '{container_name}'"
    return "\n".join(buffer)

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


SYSTEM_PROMPT = """
You are an expert DevOps engineer monitoring live container logs.

Your job is described as follows:
    1. Call get_recent_logs for each container you are asked to check.
    2. Read the logs **very carefully**. Look for:
        - ERROR or CRITICAL level messages
        - Repeated failures or retries
        - Resource exhaustion (memory, disk, connections, etc,.)
        - Timeouts or cascading failures
    3. For each REAL issue found, call report_anomaly once with severity, container, description, and fix.
    4. If logs look healthy (i.e. **ONLY** INFO / DEBUG), do **NOT** call report_anomaly. Just say "Logs Healthy."

Be concise and precise. Only report actual problems, not normal INFO traffic.
"""

def build_agent():
    llm = ChatGroq(
        model=os.getenv("LLM_MODEL", "llama3-8b-8192"),
        groq_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_tokens=1024,
    )

    tools = [get_recent_logs, report_anomaly]

    prompt = ChatPromptTemplate.from_messages([
        ("systems", SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=8,
    )
