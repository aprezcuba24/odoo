# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Odoo 19.0 — a Python ERP/business-apps framework — installed directly on a Debian/Ubuntu VPS (no Docker) and managed via systemd, with an **external** PostgreSQL database. The Odoo core lives in `odoo/` and the standard addons in `addons/`. Custom deployment logic is entirely in the root-level files.

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

Code lives at `/apps/odoo`. The setup script is idempotent and can be re-run after `git pull`.

```bash
sudo bash deploy.sh
```

Manage via systemd:

```bash
sudo systemctl status odoo
sudo journalctl -u odoo -f
sudo systemctl restart odoo    # after editing /apps/odoo/.env
```

In the server I do the following
```
sudo cp /apps/odoo/odoo.service /etc/systemd/system/odoo.service
```

## Architecture of custom deployment files

| File | Purpose |
|------|---------|
| `docker-entrypoint.sh` | Entry point for both Docker and systemd. Checks if DB is initialized (queries `ir_module_module`), runs `db init` on first run or `module upgrade base` on subsequent deploys, then `exec`s Gunicorn. |
| `odoo-wsgi.py` | WSGI application. Parses `DATABASE_URL` (or `PG*` vars) into Odoo config, sets `gevent_port = http_port` (required for WebSocket auth), wraps `odoo.http.root` with `WebSocketMiddleware`. |
| `gunicorn.conf.py` | Gunicorn configuration. All settings read from env vars. Uses `GeventWorkerWithSocket` worker class by default. Sets `preload_app=False` (required with gevent + WebSockets). |
| `gunicorn_gevent_handler.py` | Custom gevent Gunicorn worker (`GeventWorkerWithSocket`) and handler (`GeventWSGIHandler`). Injects the raw TCP socket into `environ['socket']` so Odoo can take over the connection for WebSocket upgrades. Suppresses expected `EBADF` errors after upgrade. |
| `odoo.service` | systemd unit. Loads `/apps/odoo/.env`, runs `docker-entrypoint.sh` as the `odoo` user. `TimeoutStartSec=600` to allow DB init on first run. |
| `deploy.sh` | One-shot VPS setup: installs system packages, Python 3.12 (deadsnakes PPA), wkhtmltopdf 0.12.6.1, creates `odoo` user, creates virtualenv at `venv/`, installs `requirements.txt` + `gunicorn[gevent]`, creates `.env`, installs and enables the systemd service. |

## Environment variables

`DATABASE_URL` (preferred) or individual `PG*` vars (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`).

First-run initialization vars: `DB_LANGUAGE` (default `es_ES`), `DB_USERNAME` (default `admin`), `DB_PASSWORD_ADMIN`, `DB_WITH_DEMO` (`true`/`false`).

Gunicorn vars: `GUNICORN_BIND`, `GUNICORN_WORKERS`, `GUNICORN_WORKER_CLASS`, `GUNICORN_TIMEOUT`, `GUNICORN_KEEPALIVE`, `GUNICORN_LOG_LEVEL`, `GUNICORN_ACCESS_LOG`, `GUNICORN_ERROR_LOG`.

## WebSocket notes

Odoo's WebSocket endpoint (`/websocket`) requires:
1. Gunicorn worker class must be `gevent` (specifically `GeventWorkerWithSocket` here).
2. `gevent_port` in Odoo config must equal the HTTP port (set in `odoo-wsgi.py`).
3. `preload_app` must be `False`.
4. Reverse proxy must forward `Upgrade` and `Connection` headers (HTTP/1.1).

The custom handler in `gunicorn_gevent_handler.py` exists specifically to solve the socket-handoff problem: after Odoo responds `101 Switching Protocols`, it takes over the raw socket. Gunicorn then sees `EBADF` when it tries to read the next request — this is expected and suppressed.
