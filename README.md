# Odoo 19 (this repository)

This tree is **Odoo 19** with deployment tooling (Docker, Gunicorn + gevent for WebSockets). Custom addons live under [`own_modules/`](own_modules/).

- [Odoo documentation](https://www.odoo.com/documentation/master)
- [Odoo security disclosure](https://www.odoo.com/security-report)

---

## Custom addons (`own_modules`)

Odoo only sees modules that sit on the **addons path**. For this project that means:

| Location | Role |
|----------|------|
| `odoo/addons` | Odoo core addons |
| `addons` | Standard/community addons shipped in this repo |
| `own_modules` | Your custom modules (e.g. `order_bridge`, `mcp_api`) |
| `oca` | OCA addons vendored here (e.g. `server_environment`, `fs_storage`, `fs_attachment` for Odoo 19) |

**Ways to configure it**

1. **Environment variable (recommended for Docker / [Railway](https://railway.com/))**
   Set `ODOO_ADDONS_PATH` to a comma-separated list of directories (no spaces). Example:

   ```bash
   ODOO_ADDONS_PATH=/app/odoo/addons,/app/addons,/app/own_modules,/app/oca
   ```

   In the production Docker image, [`docker-entrypoint.sh`](docker-entrypoint.sh) sets this by default if `ODOO_ADDONS_PATH` is unset, so `own_modules` and `oca` are included without extra configuration.

2. **CLI (local runs without env)**

   ```bash
   python3 odoo-bin --addons-path=odoo/addons,addons,own_modules,oca …
   ```

After changing paths or adding modules, install or upgrade the app from **Apps** in Odoo, or use `-i` / `-u` on the CLI (see below).

---

## Deploy on Railway (Docker)

Production runs on [Railway](https://railway.com/) as a **Docker** web service with managed PostgreSQL. Railway docs: [railway.com/docs](https://docs.railway.com/). See also [`docs/RAILWAY.md`](docs/RAILWAY.md) for a focused Railway reference.

### Quick deploy

1. Create a **New Project** in the [Railway dashboard](https://railway.com/dashboard).
2. Add a **PostgreSQL** service (Railway provisions it and can inject `DATABASE_URL` into the web service).
3. Add a **service from GitHub repo** (or Docker image) pointing at this repository; Railway uses the root [`Dockerfile`](Dockerfile).
4. Link `DATABASE_URL` from the Postgres service to the Odoo service (Railway **Variables** → reference the Postgres plugin variable).
5. Set at least: `DATABASE_URL`, `DB_PASSWORD_ADMIN`, and optionally `DB_LANGUAGE`, `DB_USERNAME`, `DB_WITH_DEMO`. See [`.env.example`](.env.example) for the full list.
6. Expose **port `8069`** (Railway detects it from the Dockerfile; confirm in service **Settings → Networking**).
7. Add a **custom domain** (or use the generated `*.up.railway.app` URL) under **Settings → Public Networking**.

### Railway-specific notes

- **Private networking**: App and Postgres in the same project communicate over Railway’s internal network; use the injected `DATABASE_URL`.
- **WebSockets**: Supported out of the box (HTTP, TCP, WebSockets). The custom Gunicorn gevent worker in this repo handles Odoo’s `/websocket` endpoint.
- **Ephemeral filesystem**: Container disk is not durable across deploys. Use database attachment storage (default in [`docker-entrypoint.sh`](docker-entrypoint.sh)) or S3 via `fs_attachment` (see `.env.example`).
- **Deploy upgrades**: Each deploy runs `odoo-bin -u base` before Gunicorn starts (2–5 minutes). The Dockerfile healthcheck uses a long `start-period` for this.
- **Logs**: stdout/stderr appear in the Railway service **Logs** tab.
- **Multi-tenant**: A separate Railway **project** is planned for multi-database hosting; the current production project stays single-tenant (one database).

### Other PaaS

The same Docker image also works on other platforms. [`SEENODE_DEPLOYMENT.md`](SEENODE_DEPLOYMENT.md) documents a legacy Seenode flow. Railway is the supported production target for this repository.

---

## Run locally

### Dev Container (recommended)

1. Open the repo in VS Code / Cursor and **Reopen in Container** (uses [`.devcontainer/docker-compose.yml`](.devcontainer/docker-compose.yml)).
2. The app container sets `ODOO_ADDONS_PATH`, **`ODOO_DATA_DIR=/app/.odoo_data`** (writable filestore on the bind mount), and **`ODOO_LIMIT_TIME_REAL=0`** so asset-bundle requests are not aborted after 120s (needed when attachments go to remote storage via `fs_attachment`). The service runs:

   ```bash
   python3 odoo-bin --dev=all -d odoo
   ```

   Outside this compose stack, pass `--limit-time-real=0` (or export `ODOO_LIMIT_TIME_REAL=0`) if the web UI hangs on load while logs show “virtual real time limit … reached” on `/web/assets/...`.

3. Open `http://localhost:8069`. Create the database **`odoo`** once (manager UI or `odoo-bin db … init odoo`) if it does not exist. Postgres user/password in compose: `odoo` / `odoo`.

### Docker Compose from the host (no IDE)

From the repository root:

```bash
docker compose -f .devcontainer/docker-compose.yml up --build
```

Same URL and DB defaults as above.

### Remove the dev database (reset)

This wipes the **PostgreSQL database named `odoo`** used by the devcontainer / compose stack. All Odoo data in that database is lost. Stop Odoo first so no session holds the database open.

**Using container names** (matches [`.devcontainer/docker-compose.yml`](.devcontainer/docker-compose.yml)):

```bash
docker stop odoo-app
docker start odoo-postgres   # only if Postgres is not already running
docker exec odoo-postgres psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS odoo;"
docker start odoo-app
```

After restart, Odoo recreates an empty `odoo` database on first use (`-d odoo`).

**Optional — clear the filestore** (attachments and local data under the bind mount). From the repository root, with Odoo stopped:

```bash
rm -rf .odoo_data
```

**Using Docker Compose** from the repository root (same effect):

```bash
docker compose -f .devcontainer/docker-compose.yml stop app
docker compose -f .devcontainer/docker-compose.yml start postgres
docker compose -f .devcontainer/docker-compose.yml exec postgres psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS odoo;"
docker compose -f .devcontainer/docker-compose.yml start app
```

### Odoo CLI (PostgreSQL already running)

With dependencies installed and working directory at the repo root:

```bash
export ODOO_ADDONS_PATH=odoo/addons,addons,own_modules,oca
python3 odoo-bin --dev=all --db_host=HOST --db_port=5432 -r USER -w PASSWORD -d DATABASE
```

Examples:

```bash
# First-time database (replace connection flags as needed)
python3 odoo-bin db --db_host=localhost --db_port=5432 -r odoo -w odoo init odoo --language=es_ES

# Update all modules after pulling code
python3 odoo-bin -d odoo -u base --stop-after-init --no-http
```

---

## Linting (optional)

```bash
ruff check .
ruff format .
```

Configuration: [`ruff.toml`](ruff.toml).

---

## MCP (JSON-2)

Addon Odoo con métodos custom para JSON-2: [`own_modules/mcp_api`](own_modules/mcp_api/README.md). El servicio MCP (FastMCP + `OdooClient`) vive fuera de este repositorio.

Install the addon: `python3 odoo-bin -d odoo -i mcp_api --stop-after-init --no-http`

---

## Tests (`own_modules`)

Start the dev server first (e.g. `python3 odoo-bin --dev=all -d odoo` on port **8069**). Then run tests in **another terminal** so logs stay separate:

[`own_modules/scripts/run_tests.sh`](own_modules/scripts/run_tests.sh)

The script discovers addons under `own_modules/` that have a `tests/` folder and `__manifest__.py`, and runs their tests via `odoo-bin shell` and Odoo’s `run_tests()` helper. It does **not** run `-u` or bind to port 8069; the test harness uses **8070** by default. By default it only prints a **summary** (`passed` / `failed` / `total`); Odoo logs go to a temp file (shown on failure). Use `--verbose` for full Odoo output on screen.

```bash
# All own_modules tests (currently order_bridge + mcp_api)
./own_modules/scripts/run_tests.sh

# Single module
./own_modules/scripts/run_tests.sh mcp_api

# Multiple modules
./own_modules/scripts/run_tests.sh order_bridge mcp_api

# order_bridge shortcuts (module name + shortcut)
./own_modules/scripts/run_tests.sh order_bridge listener
./own_modules/scripts/run_tests.sh order_bridge store   # store state transitions
./own_modules/scripts/run_tests.sh order_bridge api     # HTTP API (HttpCase on port 8070)

# List discovered modules
./own_modules/scripts/run_tests.sh --list
```

Options:

```bash
./own_modules/scripts/run_tests.sh order_bridge listener --db odoo
./own_modules/scripts/run_tests.sh --tags '/order_bridge:TestOrderBridgeOrderCreatedListener'
./own_modules/scripts/run_tests.sh --help
./own_modules/scripts/run_tests.sh order_bridge listener --verbose
```

Defaults (devcontainer):

| Setting | Value |
|---------|--------|
| Database | `odoo` (override with `--db` or `ODOO_DB`) |
| Test HTTP port | `8070` (harness only; dev server stays on 8069; override with `--http-port` or `ODOO_TEST_HTTP_PORT`) |
| Log output | summary only (`--verbose` for full Odoo logs on screen) |
| Module update | none — upgrade modules on the running server after schema changes |
| Addons path | `odoo/addons,addons,own_modules,oca` (override with `ODOO_ADDONS_PATH`) |

Equivalent manual command:

```bash
python3 odoo-bin shell -d odoo --http-port 8070 \
  --addons-path=odoo/addons,addons,own_modules,oca <<'PY'
from odoo.tests.shell import run_tests
report = run_tests(env, 'order_bridge,mcp_api', modules=['order_bridge', 'mcp_api'])
raise SystemExit(0 if report.wasSuccessful() else 1)
PY
```

---

## Troubleshooting: broken CSS/JS (assets) locally

**1. Writable data directory**
The devcontainer sets `ODOO_DATA_DIR=/app/.odoo_data` so the filestore is on the bind mount. If `/web/assets/...` returns **500** or the UI is unstyled, check the server log: a `FileNotFoundError` under `.odoo_data/filestore/` means the **database still lists asset attachments whose files were deleted** (for example after changing `ODOO_DATA_DIR`, pruning `filestore`, or copying only the DB).

Clear those bundle rows so Odoo recreates them on the next request (same env vars as the running server, from `/app`):

```bash
python3 odoo-bin shell -d odoo --no-http <<'PY'
Att = env["ir.attachment"].sudo()
atts = Att.search([
    ("public", "=", True),
    ("url", "!=", False),
    ("url", "like", "/web/assets/%"),
    ("res_model", "=", "ir.ui.view"),
    ("res_id", "=", 0),
])
n = len(atts)
atts.unlink()
env.cr.commit()
print("removed", n, "asset attachments")
PY
```

Then hard-refresh the browser (`Ctrl+Shift+R`). If problems persist, run `python3 odoo-bin -d odoo -u web --stop-after-init --no-http` once.

# Start web
```
python3 odoo-bin --dev=all -d odoo
```

## Update the database
```
python3 odoo-bin -d odoo1 -u order_bridge --stop-after-init --no-http
```

### HTTPS in development (optional)

The devcontainer includes a **Caddy** service (`.devcontainer/docker-compose.yml`) that terminates TLS on port 443 and proxies to Odoo on port 8069. Use this when you need secure cookies, passkeys, or any API that requires `https://`.

**One-time setup** (run inside the devcontainer after starting Odoo at least once):

```bash
bash dev-https-setup.sh odoo1        # export CA cert + set web.base.url
```

The script prints OS-specific instructions for trusting Caddy's root CA in your browser.

**Start Odoo with proxy mode** so Werkzeug respects `X-Forwarded-Proto`:

```bash
python3 odoo-bin --dev=all -d odoo1 --proxy-mode
```

Then open <https://localhost>. Without `--proxy-mode`, Odoo ignores the `X-Forwarded-*` headers and generates `http://` links even though the browser sees `https://`.

python3 odoo-bin -d odoo1 -u bi_analytics --stop-after-init --no-http --load-language=es_ES,es_419