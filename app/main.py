import hmac
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

import psutil
from fastapi import FastAPI, Header, HTTPException

# Read metrics from the host's procfs, mounted read-only by Docker.
HOST_PROC = "/host/proc"
psutil.PROCFS_PATH = HOST_PROC

API_KEY = os.environ.get("MONITOR_API_KEY", "")
SERVER_NAME = os.environ.get("SERVER_NAME") or "unknown-server"
DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://docker-socket-proxy:2375").rstrip("/")
DOCKER_TIMEOUT = float(os.environ.get("DOCKER_TIMEOUT", "3"))

if not API_KEY:
    raise RuntimeError("MONITOR_API_KEY must be set")

app = FastAPI(
    title="OneByte VPS Monitor",
    version="1.1.0",
    docs_url=None,
    redoc_url=None,
)


def require_api_key(x_api_key: Annotated[str, Header()] = "") -> None:
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


def host_uptime_seconds() -> int:
    uptime_file = Path(HOST_PROC) / "uptime"
    return int(float(uptime_file.read_text().split()[0]))


def host_timezone() -> str:
    timezone_file = Path("/host/timezone")
    if timezone_file.exists():
        value = timezone_file.read_text().strip()
        if value:
            return value
    return os.environ.get("TZ", "UTC")


def docker_get(path: str):
    request_url = f"{DOCKER_API_URL}{path}"
    with urlopen(request_url, timeout=DOCKER_TIMEOUT) as response:
        return json.loads(response.read())


def container_uptime_seconds(container_id: str, state: str):
    if state != "running":
        return None

    try:
        details = docker_get(f"/containers/{quote(container_id, safe='')}/json")
        started_at = details.get("State", {}).get("StartedAt")
        if not started_at or started_at.startswith("0001-01-01"):
            return None

        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    except (OSError, ValueError, KeyError, URLError):
        return None


def docker_container_info(container: dict) -> dict:
    names = container.get("Names") or []
    name = names[0].lstrip("/") if names else container.get("Id", "unknown")[:12]
    state = (container.get("State") or "unknown").lower()
    container_id = container.get("Id", "")

    return {
        "name": name,
        "image": container.get("Image", "unknown"),
        "status": state,
        "uptime_seconds": container_uptime_seconds(container_id, state),
    }


def docker_info() -> dict:
    try:
        containers = docker_get("/containers/json?all=1")
        with ThreadPoolExecutor(max_workers=8) as executor:
            details = list(executor.map(docker_container_info, containers))

        running = sum(1 for item in details if item["status"] == "running")
        return {
            "available": True,
            "total": len(details),
            "running": running,
            "stopped": len(details) - running,
            "containers": sorted(details, key=lambda item: item["name"].lower()),
        }
    except (OSError, ValueError, URLError) as exc:
        return {
            "available": False,
            "total": 0,
            "running": 0,
            "stopped": 0,
            "containers": [],
            "error": type(exc).__name__,
        }


@app.get("/health")
def health():
    # Intentionally unauthenticated for Docker's local health check.
    return {"status": "ok"}


@app.get("/api/system")
def system_info(x_api_key: Annotated[str, Header()] = ""):
    require_api_key(x_api_key)

    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count(logical=True) or 1

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/host/root")

    return {
        "server": SERVER_NAME,
        "status": "online",
        "timestamp": datetime.now().astimezone().isoformat(),
        "timezone": host_timezone(),
        "cpu": {
            "usage_percent": round(cpu_percent, 1),
            "used_cores": round(cpu_percent * cpu_count / 100, 2),
            "total_cores": cpu_count,
        },
        "ram": {
            "used_bytes": memory.used,
            "total_bytes": memory.total,
            "usage_percent": round(memory.percent, 1),
        },
        "storage": {
            "used_bytes": disk.used,
            "total_bytes": disk.total,
            "usage_percent": round(disk.percent, 1),
        },
        "uptime_seconds": host_uptime_seconds(),
        "docker": docker_info(),
    }
