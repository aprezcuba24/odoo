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
# After first tenant:
ODOO_TENANT_DATABASES=cliente1
```

Optional:

```bash
ODOO_TENANT_DOMAIN_MAP={"tienda.com":"cliente1"}
ODOO_ATTACHMENT_STORAGE=s3
# Shared banner bucket; with ODOO_MULTI_TENANT, objects go under <bucket>/<db_name>/
ORDER_BRIDGE_BANNER_S3_BUCKET=mi-odoo-mt-banners
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=...
ODOO_EXTRA_INIT_MODULES=fs_attachment
```

Production single-tenant keeps its **own** `ORDER_BRIDGE_BANNER_S3_BUCKET` (dedicated, no `{db_name}` prefix) and must **not** set `ODOO_MULTI_TENANT`.

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
