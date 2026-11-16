# OneByte VPS Monitor

A lightweight, reusable Docker-based system metrics API for remote VPSs. Run the same image on each secondary VPS, with a separate server name, timezone, and API key per server.

The central dashboard is expected to collect metrics from these agents. This container does not host the dashboard itself.

## Current image and build status

- **GitHub repository:** [haleeth91/onebyte-vps-monitor](https://github.com/haleeth91/onebyte-vps-monitor)
- **Container image:** `ghcr.io/haleeth91/onebyte-vps-monitor:latest`
- **Registry:** GitHub Container Registry (GHCR)
- **Package visibility:** Keep the GHCR package private.
- **Latest verified build:** GitHub Actions run [#1 — successful](https://github.com/haleeth91/onebyte-vps-monitor/actions/runs/43867379235)
- **Supported platforms:** `linux/amd64` and `linux/arm64`

The workflow at `.github/workflows/docker-publish.yml` runs on pushes to `main`, version tags matching `v*`, and pull requests targeting `main`. Pushes to `main` publish the `latest` tag; version tags publish corresponding version tags. Pull requests build for validation but do not publish an image.

## Metrics and endpoints

`GET /api/system` returns:

- Server name and online status
- Host-local timestamp and timezone
- CPU usage percentage, logical core count, and estimated used cores
- Host RAM usage and percentage
- Root filesystem storage usage and percentage
- Host uptime in seconds

`GET /health` is an unauthenticated local health check for Docker.

The `/api/system` endpoint requires the `X-API-Key` request header.

## Deploy on a secondary VPS

The same image can be used on each secondary VPS. The values in `.env` are specific to that VPS.

### 1. Create the deployment directory

```bash
mkdir -p ~/onebyte-vps-monitor
cd ~/onebyte-vps-monitor
```

Copy `docker-compose.yml` from this repository into this directory. Create a local `.env` file with the following settings, adjusting the server name and timezone for the VPS:

```dotenv
GHCR_IMAGE=ghcr.io/haleeth91/onebyte-vps-monitor
IMAGE_TAG=latest
SERVER_NAME=prime.mirae.top
TZ=Asia/Colombo
MONITOR_API_KEY=REPLACE_WITH_A_UNIQUE_RANDOM_SECRET
MONITOR_BIND_IP=127.0.0.1
```

Generate a strong API key on the VPS:

```bash
openssl rand -hex 32
```

Use a different API key for every VPS. Keep `.env` private and never commit it to Git.

### 2. Authenticate to the private GHCR package

Create a **GitHub Personal Access Token (classic)** with the `read:packages` scope. Use that token to authenticate Docker on each VPS:

```bash
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u haleeth91 --password-stdin
```

Do not put the token in the Compose file or commit it to the repository. If GitHub requires it, ensure the token has access to the private package.

### 3. Pull and start the container

```bash
docker compose pull
docker compose up -d
```

Check the container and its health:

```bash
docker compose ps
curl -s http://127.0.0.1:8765/health
```

Test the authenticated metrics endpoint:

```bash
API_KEY=$(grep '^MONITOR_API_KEY=' .env | cut -d= -f2)
curl -s -H "X-API-Key: $API_KEY" http://127.0.0.1:8765/api/system
```

Expected health response:

```json
{"status":"ok"}
```

## Updating the image

When code is pushed to `main`, GitHub Actions builds and publishes a new `latest` image. Wait for the workflow to finish successfully, then run on each VPS:

```bash
docker compose pull
docker compose up -d
```

For controlled production rollouts, use a version tag in `.env`, such as `IMAGE_TAG=v1.0.1`, after pushing that tag to GitHub. Keep the previous version tag available so you can roll back by changing `IMAGE_TAG` and pulling again.

## Network security

The Compose file binds port `8765` to `127.0.0.1` by default. This is intentional during the initial setup and means the future central dashboard cannot reach the agent remotely yet.

When the dashboard is ready, change `MONITOR_BIND_IP` to a private VPN address or another deliberately selected interface. Restrict inbound TCP/8765 with the VPS firewall so only the dashboard host can connect. Do not expose this API publicly without appropriate firewall restrictions and HTTPS or a private network.

## Host metrics and container permissions

The container mounts the host's `/proc` and root filesystem read-only to read host-level metrics. It does not mount the Docker socket and does not discover or control other containers; Docker app discovery is a separate planned phase.

The container uses a read-only root filesystem, drops Linux capabilities, enables `no-new-privileges`, and mounts host paths read-only.

## Per-server configuration reference

| Variable | Purpose | Example |
|---|---|---|
| `GHCR_IMAGE` | Published container image | `ghcr.io/haleeth91/onebyte-vps-monitor` |
| `IMAGE_TAG` | Image version to run | `latest` |
| `SERVER_NAME` | Name returned by the API | `prime.mirae.top` |
| `TZ` | Server timezone | `Asia/Colombo` |
| `MONITOR_API_KEY` | Secret required by `/api/system` | Unique random value |
| `MONITOR_BIND_IP` | Host interface for port 8765 | `127.0.0.1` |

