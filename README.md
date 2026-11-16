# OneByte VPS Monitor

A lightweight, reusable Docker-based system metrics API for remote VPSs. Run the same image on each secondary VPS, with a separate server name, timezone, and API key per server.

The central dashboard collects metrics from these agents. This container does not host the dashboard itself.

## Container image

- **GitHub repository:** [haleeth91/onebyte-vps-monitor](https://github.com/haleeth91/onebyte-vps-monitor)
- **Container image:** `ghcr.io/haleeth91/onebyte-vps-monitor:latest`
- **Supported platforms:** `linux/amd64` and `linux/arm64`

The GitHub Actions workflow builds and publishes the image when changes are pushed to `main), and publishes version tags for `v*` tags.

## API

### `GET /api/system`

Requires the `X-API-Key` header. Returns server identity, timestamp/timezone, CPU, RAM, root filesystem storage, host uptime, and Docker container inventory.

The `docker` object includes:
- `available`: whether the Docker API could be queried
- `total`: total containers, including stopped containers
- `running`: containers whose Docker state is `running`
- `stopped`: all containers not currently in the `running` state
- `containers`: sorted list with container name, image, Docker state, and uptime in seconds

Container uptime is calculated from Docker's `StartedAt` value for running containers. Non-running containers have `uptime_seconds: null). If Docker inventory cannot be queried, system metrics remain available and `docker.available` is false with an error type.

### `GET /health`

Unauthenticated local health check for Docker. Returns `{"status":"ok"}`.

## Deploy on a secondary VPS

The same image and Compose file can be used on each secondary VPS. Set a unique server name and API key per VPS.

### 1. Create the deployment directory

```bash
sudo mkdir -p /opt/apps/onebyte-vps-monitor
sudo chown "$USER":"$(id -gn)" /opt/apps/onebyte-vps-monitor
cd /opt/apps/onebyte-vps-monitor
```

Copy `docker-compose.yml` from this repository into the directory. Create a local `.env` file:

```dotenv
GHCR_IMAGE=ghcr.io/haleeth91/onebyte-vps-monitor
IMAGE_TAG=latest
SERVER_NAME=prime.mirae.top
TZ=Asia/Colombo
MONITOR_API_KEY=REPLACE_WITH_A_UNIQUE_RANDOM_SECRET
MONITOR_BIND_IP=127.0.0.1
```

Generate a strong unique API key:

```bash
openssl rand -hex 32
```

Keep `.env` private and never commit it to Git.

### 2. Pull and start

Authenticate to GHCR if the package requires it, then run:

```bash
docker compose pull
docker compose up -d
docker compose ps
curl -s http://127.0.0.1:8765/health
```

Test the authenticated endpoint without sharing the key:

```bash
API_KEY=$(grep '^MONITOR_API_KEY=' .env | cut -d= -f2)
curl -s -H "X-API-Key: $API_KEY" http://127.0.0.1:8765/api/system
unset API_KEY
```

## Updating

After a successful GitHub Actions build, update each VPS:

```bash
docker compose pull
docker compose up -d
```

For controlled rollouts, pin `IMAGE_TAG` to a version tag rather than `latest`. Keep the previous image tag available for rollback.

## Docker API security

The monitoring application does **not** mount the Docker socket. Compose runs a separate Docker Socket Proxy with only the container API enabled and POST requests disabled. The proxy and monitor share a dedicated internal Docker network; the proxy is not published to the host or internet. The proxy needs access to the host Docker socket, so keep its image trusted and updated.

The monitor lists all containers, including itself and the socket-proxy helper. It only reads container metadata and start times; it does not start, stop, or modify containers.

## Host metrics and container permissions

The monitor mounts the host's `/proc` and root filesystem read-only to read host-level metrics. It uses a read-only root filesystem, drops Linux capabilities, enables `no-new-privileges`, and mounts host paths read-only.

## Configuration reference

| Variable | Purpose | Example |
|---|---|---|
| `GHCR_IMAGE` | Published image | `ghcr.io/haleeth91/onebyte-vps-monitor` |
| `IMAGE_TAG` | Image version | `latest` |
| `SERVER_NAME` | Server name returned by API | `prime.mirae.top` |
| `TZ` | Server timezone | `Asia/Colombo` |
| `MONITOR_API_KEY` | Secret for `/api/system` | Unique random value |
| `MONITOR_BIND_IP` | Host interface for port 8765 | `127.0.0.1` |
