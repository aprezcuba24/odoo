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
| `own_modules` | Your custom modules (e.g. `order_bridge`) |

**Ways to configure it**

1. **Environment variable (recommended for Docker / [Render](https://render.com/))**
   Set `ODOO_ADDONS_PATH` to a comma-separated list of directories (no spaces). Example:

   ```bash
   ODOO_ADDONS_PATH=/app/odoo/addons,/app/addons,/app/own_modules
   ```

   In the production Docker image, [`docker-entrypoint.sh`](docker-entrypoint.sh) sets this by default if `ODOO_ADDONS_PATH` is unset, so `own_modules` is included without extra configuration.

2. **CLI (local runs without env)**

   ```bash
   python3 odoo-bin --addons-path=odoo/addons,addons,own_modules …
   ```

After changing paths or adding modules, install or upgrade the app from **Apps** in Odoo, or use `-i` / `-u` on the CLI (see below).

---

## Deploy on Render (Docker)

1. Create a **Web Service** and choose **Docker**; point it at this repository (root `Dockerfile`).
2. Add **Render Postgres** (or any reachable PostgreSQL) and set a connection string as `DATABASE_URL`.
3. Set at least: `DATABASE_URL`, `DB_PASSWORD_ADMIN`, and optionally `DB_LANGUAGE`, `DB_USERNAME`, `DB_WITH_DEMO`. See [`.env.example`](.env.example) for the full list and comments.
4. Use **port `8069`** and ensure the service receives the same env vars at runtime as in your Render dashboard.

Render’s platform overview and docs: [render.com](https://render.com/) and [Render documentation](https://render.com/docs).

---

## Run locally

### Dev Container (recommended)

1. Open the repo in VS Code / Cursor and **Reopen in Container** (uses [`.devcontainer/docker-compose.yml`](.devcontainer/docker-compose.yml)).
2. The app container sets `ODOO_ADDONS_PATH` and **`ODOO_DATA_DIR=/app/.odoo_data`** (writable filestore on the bind mount). The service runs:

   ```bash
   python3 odoo-bin --dev=all -d odoo
   ```

3. Open `http://localhost:8069`. Create the database **`odoo`** once (manager UI or `odoo-bin db … init odoo`) if it does not exist. Postgres user/password in compose: `odoo` / `odoo`.

### Docker Compose from the host (no IDE)

From the repository root:

```bash
docker compose -f .devcontainer/docker-compose.yml up --build
```

Same URL and DB defaults as above.

### Odoo CLI (PostgreSQL already running)

With dependencies installed and working directory at the repo root:

```bash
export ODOO_ADDONS_PATH=odoo/addons,addons,own_modules
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
