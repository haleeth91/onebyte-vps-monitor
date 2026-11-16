import hmac
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

import psutil
from fastapi import FastAPI, Header, HTTPException

# Read metrics from the host's procfs, mounted read-only by Docker.
HOST_PROC = "/host/proc"
psutil.PROCFS_PATH = HOST_PROC

API_KEY = os.environ.get("MONITOR_API_KEY", "")
SERVER_NAME = os.environ.get("SERVER_NAME") or "unknown-server"

if not API_KEY:
    raise RuntimeError("MONITOR_API_KEY must be set")

app = FastAPI(
    title="OneByte VPS Monitor",
    version="1.0.0",
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
    }
