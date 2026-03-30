# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Odoo 19.0 — a Python ERP/business-apps framework — deployed as a Docker container on [Seenode](https://seenode.com), a modern PaaS with managed PostgreSQL. The deployment uses Gunicorn with gevent workers for WebSocket support. The Odoo core lives in `odoo/` and standard addons in `addons/`. Custom deployment logic is in the root-level Docker files.

## Development

### Local (devcontainer)

Open in VS Code and reopen in container. This spins up an Odoo app container + a local PostgreSQL 16 container (defined in `.devcontainer/docker-compose.yml`). Odoo runs directly (no Gunicorn):

```bash
python3 odoo-bin --dev=all
```

The devcontainer mounts the repo as a volume so edits are live.

### Running Odoo CLI directly

```bash
# Initialize a database
python3 odoo-bin db --db_host=HOST --db_port=5432 -r USER -w PASS init DBNAME --language=es_ES

# Update modules
python3 odoo-bin -d DBNAME -u base --stop-after-init --no-http

# Start with developer mode
python3 odoo-bin --dev=all
```

### Linting

```bash
ruff check .
ruff format .
```

Configuration is in `ruff.toml`. Import order follows Odoo conventions: `future → stdlib → third-party → odoo → odoo.addons`.

## Production deployment

This project is configured for deployment on [Seenode](https://seenode.com), a PaaS similar to Render. See `SEENODE_DEPLOYMENT.md` for detailed deployment instructions.

### Quick deploy

1. Push code to GitHub
2. Go to https://cloud.seenode.com
3. Create a managed PostgreSQL database
4. Create Web Service, connect your repo
5. Set port to `8069` and add environment variables
6. Deploy

### Environment variables

Required:
- `DATABASE_URL`: Full PostgreSQL connection string from Seenode database dashboard
- `DB_PASSWORD_ADMIN`: Master password for Odoo database management
- `DB_LANGUAGE`: Default language (e.g., `es_ES`)
- `DB_USERNAME`: Default admin username (e.g., `admin`)
- `DB_WITH_DEMO`: `true`/`false` — install demo data

Optional (deploy / Gunicorn):
- `SKIP_DB_UPGRADE`: Set `true` to skip `odoo-bin -u base` on startup (emergency; run upgrade manually with enough RAM)
- `GUNICORN_WORKERS`: Number of workers (default: **2** in Docker; use `1` on very small instances)
- `GUNICORN_TIMEOUT`: Request timeout in seconds (default: 600)
- `GUNICORN_KEEPALIVE`: Keep-alive timeout (default: 75)

## Architecture of deployment files

| File | Purpose |
|------|---------|
| `Dockerfile` | Production Docker image. Builds Python 3.12 slim image with wkhtmltopdf, installs dependencies, creates `odoo` user. Used by Seenode to build the container. |
| `docker-entrypoint.sh` | Entry point script. Checks if database is initialized (queries `ir_module_module`), runs `odoo-bin db init` on first run or `odoo-bin -u base` on subsequent deploys, then `exec`s Gunicorn. |
| `odoo-wsgi.py` | WSGI application. Parses `DATABASE_URL` into Odoo config, sets `gevent_port = http_port` (required for WebSocket auth), wraps `odoo.http.root` with `WebSocketMiddleware`. |
| `gunicorn.conf.py` | Gunicorn configuration. All settings read from env vars. Uses `GeventWorkerWithSocket` worker class by default. Sets `preload_app=False` (required with gevent + WebSockets). Uses `/tmp` for pidfile and worker temp for PaaS compatibility. |
| `gunicorn_gevent_handler.py` | Custom gevent Gunicorn worker (`GeventWorkerWithSocket`) and handler (`GeventWSGIHandler`). Injects the raw TCP socket into `environ['socket']` so Odoo can take over the connection for WebSocket upgrades. Suppresses expected `EBADF` errors after upgrade. |
| `.env.example` | Environment variable templates with Seenode-specific examples. |
| `SEENODE_DEPLOYMENT.md` | Step-by-step deployment guide for Seenode. |

## WebSocket notes

Odoo's WebSocket endpoint (`/websocket`) requires:
1. Gunicorn worker class must be `gevent` (specifically `GeventWorkerWithSocket` here).
2. `gevent_port` in Odoo config must equal the HTTP port (set in `odoo-wsgi.py`).
3. `preload_app` must be `False`.
4. Seenode's load balancer forwards WebSocket headers automatically.

The custom handler in `gunicorn_gevent_handler.py` exists specifically to solve the socket-handoff problem: after Odoo responds `101 Switching Protocols`, it takes over the raw socket. Gunicorn then sees `EBADF` when it tries to read the next request — this is expected and suppressed.

## Notes

- **RAM**: Prefer **≥1GB** for the web service on PaaS. `512MB` commonly hits OOM during deploy (`-u base`) or when browsing with multiple workers. See `SEENODE_DEPLOYMENT.md` (Memory requirements, troubleshooting).
- **No persistent volumes**: Seenode does not currently offer persistent disks. Configure attachment storage to use the database (default) or external S3-compatible storage.
- **Zero-downtime deploys**: Seenode keeps the old instance running while the new one starts and passes health checks.
- **Database upgrades**: Every deploy runs `odoo-bin -u base` to update the database schema. This takes 2-3 minutes on subsequent deploys.
- **Health checks**: The Dockerfile includes a healthcheck on `/web/health`. Seenode uses this to determine deployment health.
- **Logs**: All logs go to stdout/stderr and are visible in the Seenode dashboard. No file-based logging in production.
