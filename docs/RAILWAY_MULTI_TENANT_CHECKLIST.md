# Railway multi-tenant — checklist y guía operativa

This checklist is the operational part of the multi-tenant plan. Creating the Railway project requires your Railway account; the repo already contains the code and docs.

Follow this in the [Railway dashboard](https://railway.com/dashboard) (or [Railway CLI](https://docs.railway.com/guides/cli)).

---

## Cómo crear un nuevo tenant (instancia ya desplegada)

Usa esta sección cuando el proyecto multi-tenant **ya existe**, responde `/web/health` con **200**, y quieres añadir otro negocio (otra base de datos Odoo).

### Antes de empezar

- [ ] `ODOO_MULTI_TENANT=true` en el servicio
- [ ] `https://<tu-host>/web/health` → **200**
- [ ] Conoces el valor de `DB_PASSWORD_ADMIN` (master password + contraseña inicial del usuario `admin` del tenant nuevo)
- [ ] Eliges un **nombre de tenant** = nombre de la base de datos:
  - Solo letras, números y `_`; debe empezar por letra
  - Ejemplos: `demo`, `cliente1`, `tienda_norte`
  - Si usas subdominio (`cliente1.tuplataforma.com`), el nombre de BD **debe** coincidir con el subdominio (`cliente1`)
- [ ] Si usas banners en S3: `ODOO_ATTACHMENT_STORAGE=s3` + bucket (`ORDER_BRIDGE_BANNER_S3_BUCKET` o `ODOO_S3_BUCKET`) + credenciales (`ORDER_BRIDGE_*` o `AWS_*`)

### Paso 1 — Crear la base de datos (recomendado: UI web)

1. Abre: `https://<tu-host>/tenant/provision`  
   Ejemplo: `https://odoo-production-xxxx.up.railway.app/tenant/provision`
2. Rellena el formulario:
   - **Master password:** valor de `DB_PASSWORD_ADMIN` (Variables del servicio)
   - **Tenant / nombre BD:** p. ej. `cliente2`
   - **Módulos extra (opcional):** p. ej. `order_bridge,fs_attachment` (o deja vacío)
   - **Force recreate:** solo si quieres borrar y recrear una BD incompleta/existente
3. Pulsa crear y espera los logs hasta **Completado OK**
4. Anota: el login Odoo del tenant será `admin` (o `DB_USERNAME` si lo tienes definido) y la contraseña inicial será el **`DB_PASSWORD_ADMIN` actual** del servicio

### Paso 1 (alternativa) — CLI en Railway shell

Preferible el shell del servicio (no desde tu PC: el proxy público a Postgres a menudo se cuelga).

```bash
cd /app
./scripts/provision_tenant.sh cliente2
# con módulos extra:
# ./scripts/provision_tenant.sh cliente2 order_bridge,fs_attachment
```

El script es **idempotente**: BD lista → no reinicia; incompleta → recrea. Forzar:

```bash
PROVISION_FORCE_RECREATE=true ./scripts/provision_tenant.sh cliente2
```

### Paso 2 — Registrar el tenant para los deploys

En Railway → Variables del servicio Odoo, **añade** el nombre a la lista (no sustituyas los que ya existen):

```bash
# Antes:  ODOO_TENANT_DATABASES=demo
# Después:
ODOO_TENANT_DATABASES=demo,cliente2
```

Así cada deploy ejecuta `odoo-bin -u base` también sobre `cliente2`.

### Paso 3 — Enrutar el host al tenant nuevo

Elige **una** forma de acceso:

#### A) Subdominio wildcard (producción típica)

Si ya tienes `*.tuplataforma.com` en Railway:

1. DNS / Railway ya resuelve `cliente2.tuplataforma.com` → el servicio Odoo
2. Con `ODOO_DBFILTER=^%d$` **no** hace falta mapa: el host `cliente2.…` selecciona la BD `cliente2`
3. Abre `https://cliente2.tuplataforma.com` → login Odoo

#### B) Dominio personalizado del cliente (`tienda.com`)

1. Añade el dominio en Railway → Settings del servicio
2. Actualiza `ODOO_TENANT_DOMAIN_MAP` (JSON, host **sin** `https://`):

```bash
ODOO_TENANT_DOMAIN_MAP={"odoo-production-xxxx.up.railway.app":"demo","tienda.com":"cliente2"}
```

3. Redeploy (o reinicia el servicio para que lea las variables)

#### C) Misma URL Railway por defecto (`*.up.railway.app`)

La URL Railway **solo puede apuntar a un tenant a la vez** vía el mapa (un host → una BD).  
Si ya mapeaste esa URL a `demo`, un tenant nuevo **no** se abre ahí: usa subdominio (A) o dominio propio (B).

Para cambiar qué tenant sirve la URL Railway (solo si lo necesitas):

```bash
ODOO_TENANT_DOMAIN_MAP={"odoo-production-xxxx.up.railway.app":"cliente2"}
```

### Paso 4 — Redeploy y entrar

1. Guarda las Variables y deja que Railway redeploye (o **Redeploy** manual)
2. En Logs, confirma que no falla el upgrade de `cliente2`
3. Abre la URL del paso 3
4. Login:
   - Usuario: `admin` (salvo que `DB_USERNAME` diga otra cosa)
   - Contraseña: valor de **`DB_PASSWORD_ADMIN`** en el momento del provision

### Checklist rápido (tenant nuevo)

- [ ] Provision OK (`/tenant/provision` o CLI)
- [ ] `ODOO_TENANT_DATABASES` incluye el nombre nuevo
- [ ] Acceso: subdominio **o** entrada en `ODOO_TENANT_DOMAIN_MAP`
- [ ] Redeploy
- [ ] Login con `admin` + `DB_PASSWORD_ADMIN`
- [ ] Si usas S3 banners: ver sección siguiente

### Banners / imágenes en S3 (multi-tenant)

Sin esto, las imágenes de banners y productos se guardan en Postgres y **no** aparecen en el bucket.

Variables obligatorias en el servicio MT:

```bash
ODOO_ATTACHMENT_STORAGE=s3
ORDER_BRIDGE_BANNER_S3_BUCKET=<bucket>   # preferido
# o, si no defines ORDER_BRIDGE_*:
# ODOO_S3_BUCKET=<bucket>                # fallback leído por order_bridge hooks
ORDER_BRIDGE_BANNER_S3_ACCESS_KEY_ID=... # o AWS_ACCESS_KEY_ID
ORDER_BRIDGE_BANNER_S3_SECRET_ACCESS_KEY=... # o AWS_SECRET_ACCESS_KEY
ORDER_BRIDGE_BANNER_S3_REGION=us-east-1  # o AWS_DEFAULT_REGION
ODOO_EXTRA_INIT_MODULES=fs_attachment    # order_bridge se añade al provision si hay bucket
```

Layout: `s3://<bucket>/<nombre_tenant>/...` (`directory_path=<bucket>/{db_name}`).

El hook `provision_media_fs_storage` (alias: `provision_banner_fs_storage`) crea/actualiza `fs.storage` code `s3_order_bridge_banners` con:

- `model_xmlids=order_bridge.model_order_bridge_banner` (OCA resuelve por `model_xmlids` / `field_xmlids`, **no** por `ir.model.storage_id`)
- `field_xmlids` auto-descubiertos en cada tenant: campos binarios `attachment=True` cuyo nombre contiene `image`
- `use_as_default_for_attachments=False` (assets JS/CSS siguen en DB)

Tras provision o redeploy:

1. Verificación rápida: `./scripts/verify_s3_storage.sh <tenant>`
2. En Odoo del tenant: Settings / FS Storage → registro `s3_order_bridge_banners` con `directory_path` tipo `mi-bucket/{db_name}`
3. Sube un banner **nuevo** y una imagen de producto **nueva** (o re-guarda) y comprueba el objeto en S3 bajo el prefijo del tenant
4. Imágenes creadas **antes** de configurar S3 quedan en DB hasta re-guardarlas

Remediación en un tenant ya existente (Railway shell), después de setear Variables y tener módulos instalados:

```bash
./scripts/verify_s3_storage.sh demo

# forzar crear/actualizar fs.storage (imprime traceback si falla):
./scripts/provision_s3_storage.sh demo

# o a mano:
printf '%s\n' \
  "from odoo.addons.order_bridge import hooks as obhooks" \
  "obhooks.provision_media_fs_storage(env)" \
  "env.cr.commit()" \
| python3 odoo-bin shell -d demo --db_host="$PGHOST" --db_port="${PGPORT:-5432}" -r "$PGUSER" -w "$PGPASSWORD" --no-http
```

(o un redeploy: el entrypoint corre `provision_banner_s3` → `provision_media_fs_storage` sobre cada BD en `ODOO_TENANT_DATABASES`).

### Contraseñas (importante)

| Variable / valor | Para qué sirve |
|------------------|----------------|
| `DB_PASSWORD_ADMIN` | Master password de `/tenant/provision` **y** contraseña inicial del usuario `admin` **al crear** el tenant |
| Cambiar `DB_PASSWORD_ADMIN` después | **No** cambia la contraseña de tenants ya creados |
| `admin` / `admin` | Solo si el provision corrió **sin** `DB_PASSWORD_ADMIN` en el entorno |

Si no puedes entrar a un tenant ya creado, resetea la contraseña desde el **Railway shell** del servicio (ver [`RAILWAY.md`](RAILWAY.md) / soporte operativo); no basta con editar Variables.

### Ejemplo completo

Ya tienes `demo` en `https://odoo-production-14fc.up.railway.app` (mapeado). Quieres `cliente2` en subdominio:

1. UI: `/tenant/provision` → tenant `cliente2` → Completado OK  
2. `ODOO_TENANT_DATABASES=demo,cliente2`  
3. Abre `https://cliente2.tuplataforma.com` (wildcard ya configurado)  
4. Login `admin` + `DB_PASSWORD_ADMIN`  
5. Redeploy para que el próximo deploy también actualice `cliente2`

---

## Safety (proyecto nuevo)

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
# Required: ODOO_ATTACHMENT_STORAGE=s3 (otherwise attachments stay in Postgres).
ODOO_ATTACHMENT_STORAGE=s3
ORDER_BRIDGE_BANNER_S3_BUCKET=mi-odoo-mt-banners
# ODOO_S3_BUCKET=mi-odoo-mt-banners  # fallback if ORDER_BRIDGE_BANNER_S3_BUCKET unset
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

## First tenant (bootstrap)

Same flow as [Cómo crear un nuevo tenant](#cómo-crear-un-nuevo-tenant-instancia-ya-desplegada), plus map the Railway default URL if you have no wildcard yet:

```bash
ODOO_TENANT_DATABASES=demo
ODOO_TENANT_DOMAIN_MAP={"tu-servicio.up.railway.app":"demo"}
```

Then redeploy and open the service URL.

## Verify production untouched

- [ ] Production project env: `ODOO_MULTI_TENANT` is **absent** or `false`
- [ ] Production URL still serves the original single database

## Reference

- [`docs/RAILWAY.md`](RAILWAY.md)
- [`.env.example`](../.env.example)
- [`scripts/provision_tenant.sh`](../scripts/provision_tenant.sh)
- [`own_modules/tenant_routing`](../own_modules/tenant_routing)
