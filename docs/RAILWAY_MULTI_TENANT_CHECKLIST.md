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

## First tenant

From a machine that can reach Postgres (Railway shell, local with public URL, or one-off):

```bash
export DATABASE_URL='...'   # same as the multi-tenant service
export DB_PASSWORD_ADMIN='...'
./scripts/provision_tenant.sh cliente1
# optional: ./scripts/provision_tenant.sh cliente1 order_bridge,fs_attachment
```

- [ ] Set `ODOO_TENANT_DATABASES=cliente1` and redeploy
- [ ] Open `https://cliente1.tuplataforma.com` and verify login

## Verify production untouched

- [ ] Production project env: `ODOO_MULTI_TENANT` is **absent** or `false`
- [ ] Production URL still serves the original single database

## Reference

- [`docs/RAILWAY.md`](RAILWAY.md)
- [`.env.example`](../.env.example)
- [`scripts/provision_tenant.sh`](../scripts/provision_tenant.sh)
- [`own_modules/tenant_routing`](../own_modules/tenant_routing)
