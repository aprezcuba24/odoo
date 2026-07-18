# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Odoo 19.0 — a Python ERP/business-apps framework — deployed as a Docker container on [Railway](https://railway.com/), a PaaS with managed PostgreSQL. The deployment uses Gunicorn with gevent workers for WebSocket support. The Odoo core lives in `odoo/` and standard addons in `addons/`. Custom deployment logic is in the root-level Docker files.

## Development

### Local (devcontainer)

Open in VS Code and reopen in container. This spins up an Odoo app container + a local PostgreSQL 16 container (defined in `.devcontainer/docker-compose.yml`). Compose sets `ODOO_LIMIT_TIME_REAL=0` so slow asset generation + `fs_attachment` S3 uploads are not killed by Odoo’s default 120s per-request limit (which otherwise reloads the server and blanks the UI). Odoo runs directly (no Gunicorn):

```bash
python3 odoo-bin --dev=all
```

If running Odoo without that env, use `python3 odoo-bin --dev=all --limit-time-real=0` when remote attachment storage causes long `/web/assets/...` requests.

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

This project is configured for deployment on [Railway](https://railway.com/) as a **Docker** web service. See the **Deploy on Railway (Docker)** section in `README.md` and [Railway documentation](https://docs.railway.com/) for platform details.

### Quick deploy

1. Push code to GitHub (or another Git provider Railway supports)
2. Open [Railway Dashboard](https://railway.com/dashboard) and create a **New Project**
3. Add **PostgreSQL** and link `DATABASE_URL` to the Odoo service
4. Deploy from this repo (root `Dockerfile`), expose **port `8069`**
5. Add the environment variables below
6. Deploy

### Environment variables

Required:
- `DATABASE_URL`: Full PostgreSQL connection string (from Railway Postgres or your provider)
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
| `Dockerfile` | Production Docker image. Builds Python 3.12 slim image with wkhtmltopdf, installs dependencies, creates `odoo` user. Used by Railway to build the container. |
| `docker-entrypoint.sh` | Entry point script. Checks if database is initialized (queries `ir_module_module`), runs `odoo-bin db init` on first run or `odoo-bin -u base` on subsequent deploys, then `exec`s Gunicorn. |
| `odoo-wsgi.py` | WSGI application. Parses `DATABASE_URL` into Odoo config, sets `gevent_port = http_port` (required for WebSocket auth), wraps `odoo.http.root` with `WebSocketMiddleware`. |
| `gunicorn.conf.py` | Gunicorn configuration. All settings read from env vars. Uses `GeventWorkerWithSocket` worker class by default. Sets `preload_app=False` (required with gevent + WebSockets). Uses `/tmp` for pidfile and worker temp for PaaS compatibility. |
| `gunicorn_gevent_handler.py` | Custom gevent Gunicorn worker (`GeventWorkerWithSocket`) and handler (`GeventWSGIHandler`). Injects the raw TCP socket into `environ['socket']` so Odoo can take over the connection for WebSocket upgrades. Suppresses expected `EBADF` errors after upgrade. |
| `.env.example` | Environment variable templates (including values useful for local dev and Railway). |
| `README.md` | Includes **Deploy on Railway (Docker)** steps and `ODOO_ADDONS_PATH` notes. |
| `docs/RAILWAY.md` | Focused Railway deployment reference for this repository. |
| `SEENODE_DEPLOYMENT.md` | Legacy step-by-step guide for Seenode; Railway flow is documented in `README.md`. |

## WebSocket notes

Odoo's WebSocket endpoint (`/websocket`) requires:
1. Gunicorn worker class must be `gevent` (specifically `GeventWorkerWithSocket` here).
2. `gevent_port` in Odoo config must equal the HTTP port (set in `odoo-wsgi.py`).
3. `preload_app` must be `False`.
4. Railway’s edge/proxy supports WebSockets automatically for HTTP services.

The custom handler in `gunicorn_gevent_handler.py` exists specifically to solve the socket-handoff problem: after Odoo responds `101 Switching Protocols`, it takes over the raw socket. Gunicorn then sees `EBADF` when it tries to read the next request — this is expected and suppressed.

## Notes

- **Filestore / disks**: By default the service filesystem is ephemeral. Use database attachment storage (default), [Railway volumes](https://docs.railway.com/guides/volumes) if needed, or external S3-compatible storage for a durable filestore.
- **Deploys**: Railway redeploys on git push; configure health checks so the new instance is healthy before traffic switches.
- **Database upgrades**: Every deploy runs `odoo-bin -u base` to update the database schema. This takes 2-3 minutes on subsequent deploys.
- **Health checks**: The Dockerfile includes a healthcheck on `/web/health`. Railway uses this during deploys when configured.
- **Logs**: All logs go to stdout/stderr and appear in the Railway dashboard. No file-based logging in production.
- **Multi-tenant**: Implemented as a **separate Railway project** (`ODOO_MULTI_TENANT=true`, `dbfilter`, `tenant_routing` for domain map + `/tenant/provision`, `scripts/provision_tenant.sh`). See `docs/RAILWAY.md`. The current production project remains single-tenant (do not set that env var there).
