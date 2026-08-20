# Deploy Odoo on Railway

This repository runs in production on [Railway](https://railway.com/) — an all-in-one cloud platform with managed PostgreSQL, automatic SSL, and WebSocket support.

**Primary guide:** [README.md — Deploy on Railway](../README.md#deploy-on-railway-docker)

## Why Railway

- **Docker-native**: Point at this repo; Railway builds the root [`Dockerfile`](../Dockerfile).
- **Managed PostgreSQL**: Add a Postgres service; reference `DATABASE_URL` in the Odoo service.
- **Private networking**: Services in the same project reach each other without public exposure.
- **WebSockets**: HTTP, TCP, and WebSocket traffic handled automatically (required for Odoo Discuss and live updates).
- **Custom domains**: Per-service domains, including [wildcard domains](https://docs.railway.com/networking/domains/working-with-domains) for optional multi-company API subdomains.

## Project layout (current production — single-tenant)

| Railway resource | Role |
|------------------|------|
| Web service (Docker) | Odoo + Gunicorn gevent on port **8069** |
| PostgreSQL | Single Odoo database (single-tenant) |

**Do not set `ODOO_MULTI_COMPANY_S3` or install `company_onboarding` on this project.** Production stays single-tenant.

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

## Multi-company (una sola BD)

Proyecto Railway **aparte** (Postgres propio). Varias `res.company` en la misma base. Onboarding self-service vía módulo `company_onboarding`.

**Guía paso a paso (proteger producción single-tenant):** [`DESPLIEGUE_MULTI_COMPANY.md`](DESPLIEGUE_MULTI_COMPANY.md)

**[`RAILWAY_MULTI_COMPANY_CHECKLIST.md`](RAILWAY_MULTI_COMPANY_CHECKLIST.md)** — checklist técnico.

No uses este modo en el single-tenant de producción.

| Pieza | Detalle |
|-------|---------|
| Modo | Una BD; muchas `res.company` |
| Acceso web | Un dominio; aislamiento por usuario (`company_ids`) |
| Acceso API | `company_slug` / `X-Company-Slug` / subdominio |
| Onboarding | `/web/signup` + wizard «Crear mi compañía» |
| S3 | `ODOO_MULTI_COMPANY_S3=true` → prefijo `{company_id}` |

---

## Other platforms

- [`RAILWAY_MULTI_COMPANY_CHECKLIST.md`](RAILWAY_MULTI_COMPANY_CHECKLIST.md) — multi-company (1 BD)
- [`SEENODE_DEPLOYMENT.md`](../SEENODE_DEPLOYMENT.md) — legacy Seenode
- [`WEBSOCKET_SERVERLESS.md`](WEBSOCKET_SERVERLESS.md) — WebSockets en PaaS

## Links

- [Railway](https://railway.com/)
- [Railway documentation](https://docs.railway.com/)
- [Railway domains](https://docs.railway.com/networking/domains)
- [Odoo 19 deployment docs](https://www.odoo.com/documentation/19.0/administration/on_premise/deploy.html)
