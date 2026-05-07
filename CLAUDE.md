# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Odoo 19.0 — a Python ERP/business-apps framework — deployed as a Docker container on [Render](https://render.com/), a PaaS with managed PostgreSQL ([Render Postgres](https://render.com/docs/databases)). The deployment uses Gunicorn with gevent workers for WebSocket support. The Odoo core lives in `odoo/` and standard addons in `addons/`. Custom deployment logic is in the root-level Docker files.

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

This project is configured for deployment on [Render](https://render.com/) as a **Docker** web service. See the **Deploy on Render (Docker)** section in `README.md` and [Render documentation](https://render.com/docs) for platform details.

### Quick deploy

1. Push code to GitHub (or another Git provider Render supports)
2. Open [Render Dashboard](https://dashboard.render.com)
3. Create **Render Postgres** (or any reachable PostgreSQL) and copy the **Internal Database URL** (or external URL if the web service is not on Render’s private network)
4. Create a **Web Service**, choose **Docker**, connect the repo, set **port `8069`**
5. Add the environment variables below
6. Deploy

### Environment variables

Required:
- `DATABASE_URL`: Full PostgreSQL connection string (from Render Postgres or your provider)
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
| `Dockerfile` | Production Docker image. Builds Python 3.12 slim image with wkhtmltopdf, installs dependencies, creates `odoo` user. Used by Render to build the container. |
| `docker-entrypoint.sh` | Entry point script. Checks if database is initialized (queries `ir_module_module`), runs `odoo-bin db init` on first run or `odoo-bin -u base` on subsequent deploys, then `exec`s Gunicorn. |
| `odoo-wsgi.py` | WSGI application. Parses `DATABASE_URL` into Odoo config, sets `gevent_port = http_port` (required for WebSocket auth), wraps `odoo.http.root` with `WebSocketMiddleware`. |
| `gunicorn.conf.py` | Gunicorn configuration. All settings read from env vars. Uses `GeventWorkerWithSocket` worker class by default. Sets `preload_app=False` (required with gevent + WebSockets). Uses `/tmp` for pidfile and worker temp for PaaS compatibility. |
| `gunicorn_gevent_handler.py` | Custom gevent Gunicorn worker (`GeventWorkerWithSocket`) and handler (`GeventWSGIHandler`). Injects the raw TCP socket into `environ['socket']` so Odoo can take over the connection for WebSocket upgrades. Suppresses expected `EBADF` errors after upgrade. |
| `.env.example` | Environment variable templates (including values useful for local dev and Render). |
| `README.md` | Includes **Deploy on Render (Docker)** steps and `ODOO_ADDONS_PATH` notes. |
| `SEENODE_DEPLOYMENT.md` | Legacy step-by-step guide for Seenode; Render flow is documented in `README.md`. |

## WebSocket notes

Odoo's WebSocket endpoint (`/websocket`) requires:
1. Gunicorn worker class must be `gevent` (specifically `GeventWorkerWithSocket` here).
2. `gevent_port` in Odoo config must equal the HTTP port (set in `odoo-wsgi.py`).
3. `preload_app` must be `False`.
4. Render’s edge/proxy supports WebSockets for web services (see [WebSocket connections](https://render.com/docs/websocket)).

The custom handler in `gunicorn_gevent_handler.py` exists specifically to solve the socket-handoff problem: after Odoo responds `101 Switching Protocols`, it takes over the raw socket. Gunicorn then sees `EBADF` when it tries to read the next request — this is expected and suppressed.

## Notes

- **Filestore / disks**: By default the service filesystem is ephemeral. Use database attachment storage (default), [Render disks](https://render.com/docs/disks), or external S3-compatible storage for a durable filestore.
- **Deploys**: Render performs rolling deploys so a new instance can become healthy before traffic moves over (plan and service type affect exact behavior; see Render docs).
- **Database upgrades**: Every deploy runs `odoo-bin -u base` to update the database schema. This takes 2-3 minutes on subsequent deploys.
- **Health checks**: The Dockerfile includes a healthcheck on `/web/health`. Configure a matching HTTP health check path in the Render service if you rely on it for deploy gates.
- **Logs**: All logs go to stdout/stderr and appear in the Render dashboard. No file-based logging in production.
