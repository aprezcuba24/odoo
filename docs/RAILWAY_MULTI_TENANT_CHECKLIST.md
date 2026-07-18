# Railway multi-tenant project — operator checklist

This checklist is the operational part of the multi-tenant plan. Creating the Railway project requires your Railway account; the repo already contains the code and docs.

Follow this in the [Railway dashboard](https://railway.com/dashboard) (or [Railway CLI](https://docs.railway.com/guides/cli)).

## Safety

- [ ] Keep the **existing** production Railway project unchanged (no `ODOO_MULTI_TENANT`).
- [ ] Create a **new** project with its **own** PostgreSQL (do not share the production DB).

## Create project

- [ ] New Project → name e.g. `odoo-multitenant`
- [ ] Add PostgreSQL plugin/service
- [ ] Deploy this GitHub repo as a Docker service (root `Dockerfile`)
- [ ] Expose port `8069`
- [ ] Reference Postgres `DATABASE_URL` on the Odoo service

## Environment variables (multi-tenant service only)

```bash
ODOO_MULTI_TENANT=true
ODOO_DBFILTER=^%d$
ODOO_LIST_DB=false
ODOO_PROXY_MODE=true
DB_PASSWORD_ADMIN=<strong-secret>
DB_LANGUAGE=es_ES
DB_WITH_DEMO=false
GUNICORN_WORKERS=2

# Shared S3 bucket for Tienda Apk banners (order_bridge). Same bucket for all
# tenants; objects go under <bucket>/<db_name>/ when ODOO_MULTI_TENANT=true.
ODOO_ATTACHMENT_STORAGE=s3
ORDER_BRIDGE_BANNER_S3_BUCKET=mi-odoo-mt-banners
ORDER_BRIDGE_BANNER_S3_REGION=us-east-1
# Prefer ORDER_BRIDGE_* keys; AWS_* also work as fallback in hooks.py
ORDER_BRIDGE_BANNER_S3_ACCESS_KEY_ID=...
ORDER_BRIDGE_BANNER_S3_SECRET_ACCESS_KEY=...
# ORDER_BRIDGE_BANNER_S3_ENDPOINT_URL=   # only for MinIO/R2/etc.
ODOO_EXTRA_INIT_MODULES=fs_attachment

# After first tenant (and for Railway default URL mapping, see docs):
# ODOO_TENANT_DATABASES=demo
# ODOO_TENANT_DOMAIN_MAP={"tu-servicio.up.railway.app":"demo"}
```

Optional:

```bash
ODOO_TENANT_DOMAIN_MAP={"tienda.com":"cliente1"}
```

Production single-tenant keeps its **own** `ORDER_BRIDGE_BANNER_S3_BUCKET` (dedicated bucket, no `{db_name}` prefix) and must **not** set `ODOO_MULTI_TENANT`.

## Domains

- [ ] Add wildcard `*.tuplataforma.com` on the Odoo service ([docs](https://docs.railway.com/networking/domains/working-with-domains))
- [ ] Configure DNS CNAME + verification TXT at your registrar
- [ ] For each custom domain: add in Railway Settings and in `ODOO_TENANT_DOMAIN_MAP`
- [ ] For the Railway default URL (`*.up.railway.app`): set `ODOO_TENANT_DOMAIN_MAP` (dbfilter `%d` will not match that host to a short tenant name like `demo`)

## Post-deploy health check (do this first)

If **every** URL returns 404 (including `/web/health`), server-wide modules did not load. After a good deploy, Railway **Logs** should show:

- `odoo-wsgi ready: MULTI_TENANT=True …`
- `tenant_routing: patching http.db_filter …`

Then:

- [ ] `https://<host>/web/health` → **200** (not 404)
- [ ] `https://<host>/tenant/provision` → provision form (or login if a DB is already mapped)

`ODOO_TENANT_DOMAIN_MAP` only works when `tenant_routing` is loaded (via `root.initialize()` in `odoo-wsgi.py`). Provisioning a DB alone does not fix 404 on the Railway default URL without that map + a healthy deploy.

## First tenant (recommended: web UI on the server)

After `/web/health` returns 200:

1. Open `https://<tu-servicio.up.railway.app>/tenant/provision`
2. Enter master password (`DB_PASSWORD_ADMIN`), tenant name (e.g. `demo`), optional modules
3. Watch live logs until **Completado**
4. Set `ODOO_TENANT_DATABASES=demo` and map the Railway host:

```bash
ODOO_TENANT_DOMAIN_MAP={"tu-servicio.up.railway.app":"demo"}
```

5. Redeploy and open the service URL (should reach Odoo login for `demo`)

CLI alternative (prefer Railway shell + internal `DATABASE_URL`; public proxy often hangs):

```bash
export DATABASE_URL='...'
export DB_PASSWORD_ADMIN='...'
./scripts/provision_tenant.sh demo
```

After CLI provision, you still need `ODOO_TENANT_DATABASES`, `ODOO_TENANT_DOMAIN_MAP` for the Railway URL, and a deploy that loads `tenant_routing`.

The script/UI are **idempotent**: incomplete DBs are recreated; ready DBs skip init. Force: checkbox in UI or `PROVISION_FORCE_RECREATE=true`.

- [ ] Provision via `/tenant/provision` (or CLI)
- [ ] Set `ODOO_TENANT_DATABASES` (+ `ODOO_TENANT_DOMAIN_MAP` for Railway default URL)
- [ ] Redeploy and verify login

## Verify production untouched

- [ ] Production project env: `ODOO_MULTI_TENANT` is **absent** or `false`
- [ ] Production URL still serves the original single database

## Reference

- [`docs/RAILWAY.md`](RAILWAY.md)
- [`.env.example`](../.env.example)
- [`scripts/provision_tenant.sh`](../scripts/provision_tenant.sh)
- [`own_modules/tenant_routing`](../own_modules/tenant_routing)
