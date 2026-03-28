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
2. The app container sets `ODOO_ADDONS_PATH` so `own_modules` is loaded. Default command:

   ```bash
   python3 odoo-bin --dev=all
   ```

3. Open `http://localhost:8069`. Database: `odoo` (user/password `odoo` as in compose).

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
