# OneByte VPS Monitor

A small, reusable Docker-based system metrics API for remote VPSs. The same image is intended to run on each secondary VPS; each instance has its own server name, timezone, and API key.

## Metrics

`GET /api/system` returns:

- Server name and online status
- Host-local timestamp and timezone
- CPU usage, logical core count, and estimated used cores
- Host RAM usage and percentage
- Root filesystem storage usage and percentage
- Host uptime in seconds

`GET /health` is an unauthenticated local health check for Docker.

## Supported platforms

GitHub Actions builds and publishes multi-platform images for:

- `linux/amd64`
- `linux/arm64`

## 1. Create the GitHub repository

Create a **private** repository named `onebyte-vps-monitor`, then push this project to its `main` branch:

```bash
git init
git add .
git commit -m "Initial OneByte VPS Monitor"
git branch -M main
git remote add origin git@github.com:YOUR_GITHUB_USERNAME/onebyte-vps-monitor.git
git push -u origin main
```

The GitHub Actions workflow builds the image and publishes it to GitHub Container Registry (GHCR).

The container package has its own visibility and access settings. For this project, keep the GHCR package private too, and grant each VPS read access using a GitHub personal access token (classic) with `read:packages`.

## 2. Configure a VPS

On each VPS:

```bash
mkdir -p ~/onebyte-vps-monitor
cd ~/onebyte-vps-monitor
```

Copy `docker-compose.yml` from this repository into that directory. Create a local `.env` file based on `.env.example` and set unique values for that VPS:

```dotenv
GHCR_IMAGE=ghcr.io/YOUR_GITHUB_USERNAME/onebyte-vps-monitor
IMAGE_TAG=latest
SERVER_NAME=prime.mirae.top
TZ=Asia/Colombo
MONITOR_API_KEY=REPLACE_WITH_A_UNIQUE_RANDOM_SECRET
MONITOR_BIND_IP=127.0.0.1
```

Generate a secret with:

```bash
openssl rand -hex 32
```

Keep `.env` private; never commit it to Git.

For a private GHCR package, authenticate on each VPS using a GitHub token with `read:packages`:

```bash
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

Then deploy:

```bash
docker compose pull
docker compose up -d
```

## 3. Test

```bash
API_KEY=$(grep '^MONITOR_API_KEY=' .env | cut -d= -f2)
curl -s -H "X-API-Key: $API_KEY" http://127.0.0.1:8765/api/system
```

Health check:

```bash
curl -s http://127.0.0.1:8765/health
```

## 4. Updating

After pushing a code change to `main`, wait for the GitHub Actions workflow to complete. Then, on each VPS:

```bash
docker compose pull
docker compose up -d
```

For safer production rollouts, pin `IMAGE_TAG` to a release tag (for example `v1.0.1`) instead of `latest`. Keep the previous tag available for rollback.

## Network security

The Compose file binds port `8765` to `127.0.0.1` by default. This is intentional for the initial pilot and means the primary dashboard cannot reach it remotely yet.

When the primary dashboard is ready, change `MONITOR_BIND_IP` to a private VPN address or another deliberately selected interface, and restrict inbound TCP/8765 using the VPS firewall to the primary dashboard's source IP. Do not expose the API publicly without firewall restrictions and HTTPS or a private network.

## Host metrics and permissions

The container mounts host `/proc` and `/` read-only to read host-level metrics. It does not mount the Docker socket and does not discover or control containers. Docker discovery is a separate planned phase.

The container drops Linux capabilities and runs with a read-only root filesystem. Host mounts are read-only.

## API authentication

`/api/system` requires the `X-API-Key` header. `/health` is intentionally unauthenticated for the local Docker health check. Use a different random API key on every VPS.
