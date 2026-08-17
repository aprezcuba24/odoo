# Multi-company en Railway (una sola BD)

Proyecto **aparte** del single-tenant de producción y **aparte** del multi-tenant multi-BD.

Una instancia Odoo → **una** base PostgreSQL → muchas `res.company` (una por negocio).

**No pongas** `ODOO_MULTI_TENANT` ni instales `tenant_routing` en este proyecto.
**No toques** el proyecto single-tenant de producción.

Guía de aislamiento: cada usuario entra por el **mismo dominio**; tras login, Odoo filtra por `company_ids`. La API Tienda Apk usa `company_slug` / header `X-Company-Slug` / subdominio.

---

## 1. Cómo montar el entorno multi-company

1. Railway → **New Project** (Postgres propio; no compartas el de producción).
2. Despliega este repo (Docker, puerto `8069`) y enlaza `DATABASE_URL`.
3. Variables del servicio:

```bash
# NO uses ODOO_MULTI_TENANT
ODOO_LIST_DB=false
ODOO_PROXY_MODE=true
DB_PASSWORD_ADMIN=<secreto-fuerte>
DB_LANGUAGE=es_ES
DB_WITH_DEMO=false
GUNICORN_WORKERS=2

# Módulos a instalar en el init / upgrade (ajusta según tu stack)
ODOO_EXTRA_INIT_MODULES=order_bridge,bi_analytics,company_onboarding,fs_attachment

# S3: prefijo por compañía (company_id) en un bucket compartido
ODOO_ATTACHMENT_STORAGE=s3
ODOO_MULTI_COMPANY_S3=true
ORDER_BRIDGE_BANNER_S3_BUCKET=<bucket>
ORDER_BRIDGE_BANNER_S3_REGION=us-east-1
ORDER_BRIDGE_BANNER_S3_ACCESS_KEY_ID=...
ORDER_BRIDGE_BANNER_S3_SECRET_ACCESS_KEY=...
```

4. Dominio único para el backend, p. ej. `app.tuplataforma.com`.
   Opcional: wildcard `*.tuplataforma.com` si la app móvil usa subdominio = `order_bridge_slug`.
5. Redeploy. Comprueba `https://<host>/web/health` → **200**.
6. Instala / actualiza módulos: `company_onboarding` activa signup público (`auth_signup.invitation_scope=b2c`).

---

## 2. Cómo onboardea un nuevo negocio (self-service)

1. Usuario abre `https://app.tuplataforma.com/web/signup`
2. Tras login, el asistente **Crear mi compañía** pide nombre, slug, país, moneda, teléfono
3. Se crea `res.company` + almacén/diarios (Odoo) + `order_bridge.general_settings`
4. El usuario queda con **solo** esa compañía (sin selector multi-company)
5. Puede invitar empleados desde Usuarios (asignándoles la misma compañía)

Slug: minúsculas, números y guiones (`mi-tienda`). Se usa en:

- Header `X-Company-Slug: mi-tienda`
- Body `company_slug` en `POST /api/order_bridge/register`
- Query `?company_slug=mi-tienda`
- Subdominio `mi-tienda.tuplataforma.com` (si hay wildcard)

---

## 3. Acceso

| Canal | Cómo se elige la compañía |
|-------|---------------------------|
| Backend web (`/odoo`) | Usuario autenticado → `company_ids` / `env.company` |
| API Tienda Apk | Con `ODOO_MULTI_COMPANY_S3=true`: slug / header / subdominio (sin slug → `company_slug_required`). Tras registro, el `device` guarda `company_id` |
| MCP JSON-2 | API key del usuario → su única compañía |

---

## 4. Checklist rápido

- [ ] Proyecto Railway nuevo (no producción single-tenant)
- [ ] Sin `ODOO_MULTI_TENANT`
- [ ] `company_onboarding` instalado
- [ ] Signup + wizard OK (2 compañías de prueba)
- [ ] Usuario A no ve pedidos/dispositivos/gastos de B
- [ ] API (`ODOO_MULTI_COMPANY_S3=true`): sin slug y varias compañías → `company_slug_required`
- [ ] S3: `ODOO_MULTI_COMPANY_S3=true` → `directory_path=<bucket>/{company_id}`

---

## 5. Relación con multi-tenant multi-BD

| | Multi-company (este doc) | Multi-BD ([checklist](RAILWAY_MULTI_TENANT_CHECKLIST.md)) |
|--|--------------------------|-------------------------------------------------------------|
| Aislamiento | Lógico (`company_id`) | Físico (BD separada) |
| Costo | Más bajo | Medio |
| Provisionado | Signup + wizard | `/tenant/provision` |
| Env | `ODOO_MULTI_COMPANY_S3` | `ODOO_MULTI_TENANT=true` |
