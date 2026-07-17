# Deploy Odoo on Railway

This repository runs in production on [Railway](https://railway.com/) — an all-in-one cloud platform with managed PostgreSQL, automatic SSL, and WebSocket support.

**Primary guide:** [README.md — Deploy on Railway](../README.md#deploy-on-railway-docker)

## Why Railway

- **Docker-native**: Point at this repo; Railway builds the root [`Dockerfile`](../Dockerfile).
- **Managed PostgreSQL**: Add a Postgres service; reference `DATABASE_URL` in the Odoo service.
- **Private networking**: Services in the same project reach each other without public exposure.
- **WebSockets**: HTTP, TCP, and WebSocket traffic handled automatically (required for Odoo Discuss and live updates).
- **Custom domains**: Per-service domains, including [wildcard domains](https://docs.railway.com/networking/domains/working-with-domains) for multi-tenant subdomains.

## Project layout (current production — single-tenant)

| Railway resource | Role |
|------------------|------|
| Web service (Docker) | Odoo + Gunicorn gevent on port **8069** |
| PostgreSQL | Single Odoo database (single-tenant) |

**Do not set `ODOO_MULTI_TENANT` on this project.** After merging multi-tenant code, this project stays single-tenant as long as that env var is unset.

Environment variables: see [`.env.example`](../.env.example) and the tables below (copy values into Railway **Variables**, not committed to git).

### Required variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (reference from Railway Postgres service) |
| `DB_PASSWORD_ADMIN` | Odoo master password for database manager |
| `DB_LANGUAGE` | Default language, e.g. `es_ES` |
| `DB_USERNAME` | Initial admin login, e.g. `admin` |
| `DB_WITH_DEMO` | `false` in production |

### Common optional variables

| Variable | Default | Notes |
|----------|---------|-------|
| `GUNICORN_WORKERS` | `2` | Use `1` on small plans to avoid OOM |
| `SKIP_DB_UPGRADE` | unset | Set `true` only in emergencies |
| `ODOO_ATTACHMENT_STORAGE` | `db` | Use `s3` with `fs_attachment` for durable files |
| `ODOO_ADDONS_PATH` | auto in entrypoint | Override only if needed |

## Deploy flow (single-tenant)

1. Push to the connected Git branch → Railway builds and deploys.
2. [`docker-entrypoint.sh`](../docker-entrypoint.sh) runs on container start:
   - First run: `odoo-bin db init` if the database is empty.
   - Every deploy: `odoo-bin -u base` (schema upgrade, ~2–5 min).
3. Gunicorn serves the app; healthcheck hits `/web/health`.

## Operational notes

- **RAM**: Plan for ≥1GB. `odoo-bin -u base` at deploy plus Gunicorn workers can OOM on 512MB.
- **Ephemeral disk**: Attachments default to PostgreSQL (`ir_attachment.location=db`) or S3 (`ODOO_ATTACHMENT_STORAGE=s3`).
- **Logs**: Service **Logs** tab in Railway dashboard (stdout/stderr).
- **Emergency skip upgrade**: `SKIP_DB_UPGRADE=true` — run `-u base` manually later with enough RAM.

---

## Multi-tenant (second Railway project)

Use a **new Railway project** (separate Postgres). Same Docker image; mode is env-driven.

### Checklist — create the project

Step-by-step checkbox list: [`RAILWAY_MULTI_TENANT_CHECKLIST.md`](RAILWAY_MULTI_TENANT_CHECKLIST.md).

1. In [Railway Dashboard](https://railway.com/dashboard): **New Project**.
2. Add **PostgreSQL** (dedicated instance — do not share with production).
3. Add **GitHub repo** service → root `Dockerfile`, port **8069**.
4. Link Postgres `DATABASE_URL` into the Odoo service.
5. Set multi-tenant env vars (below). **Do not** set these on the existing production project.
6. Add public networking:
   - Wildcard custom domain: `*.tuplataforma.com` ([Railway wildcard domains](https://docs.railway.com/networking/domains/working-with-domains)).
   - Optional: each customer custom domain via Settings or [Railway Domains API](https://docs.railway.com/integrations/api/manage-domains).
7. Provision the first tenant (service must reach Postgres — use Railway shell, one-off, or local with the private/public URL):

   ```bash
   export DATABASE_URL='postgresql://...'
   export DB_PASSWORD_ADMIN='...'
   ./scripts/provision_tenant.sh cliente1
   # optional modules:
   # ./scripts/provision_tenant.sh cliente1 order_bridge,fs_attachment
   ```

8. Set `ODOO_TENANT_DATABASES=cliente1` and redeploy.
9. Open `https://cliente1.tuplataforma.com` and log in.

### Multi-tenant environment variables

```bash
ODOO_MULTI_TENANT=true
ODOO_DBFILTER=^%d$
ODOO_LIST_DB=false
ODOO_PROXY_MODE=true

DATABASE_URL=postgresql://...@host:5432/railway
DB_PASSWORD_ADMIN=<strong-master-password>
DB_LANGUAGE=es_ES
DB_WITH_DEMO=false

# Upgrade these DBs on every deploy
ODOO_TENANT_DATABASES=cliente1,cliente2

# Custom domains (optional) — JSON host → database name
# ODOO_TENANT_DOMAIN_MAP={"tienda.com":"cliente1"}

GUNICORN_WORKERS=2

# Shared banner bucket (order_bridge); prefixes = <bucket>/{db_name}
ODOO_ATTACHMENT_STORAGE=s3
ORDER_BRIDGE_BANNER_S3_BUCKET=mi-odoo-mt-banners
ORDER_BRIDGE_BANNER_S3_REGION=us-east-1
ORDER_BRIDGE_BANNER_S3_ACCESS_KEY_ID=...
ORDER_BRIDGE_BANNER_S3_SECRET_ACCESS_KEY=...
ODOO_EXTRA_INIT_MODULES=fs_attachment
```

| Variable | Role |
|----------|------|
| `ODOO_MULTI_TENANT` | Enables multi-DB mode in [`odoo-wsgi.py`](../odoo-wsgi.py) and [`docker-entrypoint.sh`](../docker-entrypoint.sh) |
| `ODOO_DBFILTER` | Default `^%d$` — first subdomain = database name |
| `ODOO_LIST_DB` | Keep `false` in production (hides DB manager) |
| `ODOO_PROXY_MODE` | Trust Railway `X-Forwarded-*` headers |
| `ODOO_TENANT_DATABASES` | Explicit list for deploy-time `-u base` |
| `ODOO_TENANT_DOMAIN_MAP` | Custom host → DB; handled by [`own_modules/tenant_routing`](../own_modules/tenant_routing) |
| `ORDER_BRIDGE_BANNER_S3_BUCKET` | Shared S3 bucket for banners; with multi-tenant, path is `<bucket>/{db_name}` |
| `ORDER_BRIDGE_BANNER_S3_*` / `AWS_*` | Credentials (and optional region/endpoint) for that bucket |
| `ODOO_EXTRA_INIT_MODULES` | e.g. `fs_attachment` so banner S3 provisioning can run |

### Routing

| Host | Mechanism | Database |
|------|-----------|----------|
| `cliente1.plataforma.com` | `dbfilter` `%d` | `cliente1` |
| `tienda.com` | `ODOO_TENANT_DOMAIN_MAP` + `tenant_routing` | mapped name (e.g. `cliente1`) |

Convention: **database name = subdomain** for the wildcard case.

### Adding a tenant

```bash
./scripts/provision_tenant.sh nuevo_cliente
# Then on Railway multi-tenant service:
# - Append nuevo_cliente to ODOO_TENANT_DATABASES
# - For custom domain: add domain in Railway + entry in ODOO_TENANT_DOMAIN_MAP
```

### How the code behaves

- **Single-tenant** (`ODOO_MULTI_TENANT` unset): unchanged — init/upgrade the DB named in `DATABASE_URL`. Banner S3 uses a dedicated bucket at root (`directory_path=<bucket>`).
- **Multi-tenant**: does **not** init the Railway default DB (`railway`); upgrades each tenant DB; loads `tenant_routing` as a server-wide module. Banner S3 may share one bucket with per-DB prefixes (`directory_path=<bucket>/{db_name}` via [`order_bridge` hooks](../own_modules/order_bridge/hooks.py)).

---

## Other platforms

- [`RAILWAY_MULTI_TENANT_CHECKLIST.md`](RAILWAY_MULTI_TENANT_CHECKLIST.md) — operator checklist for the second project
- [`SEENODE_DEPLOYMENT.md`](../SEENODE_DEPLOYMENT.md) — legacy Seenode guide
- [`WEBSOCKET_SERVERLESS.md`](WEBSOCKET_SERVERLESS.md) — WebSocket troubleshooting on PaaS

## Links

- [Railway](https://railway.com/)
- [Railway documentation](https://docs.railway.com/)
- [Railway domains](https://docs.railway.com/networking/domains)
- [Odoo 19 deployment docs](https://www.odoo.com/documentation/19.0/administration/on_premise/deploy.html)
