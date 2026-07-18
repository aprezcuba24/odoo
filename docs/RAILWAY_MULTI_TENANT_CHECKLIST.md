# Multi-tenant en Railway

Proyecto **aparte** del single-tenant de producción. No pongas `ODOO_MULTI_TENANT` en producción.

Una instancia Odoo → muchas bases PostgreSQL (una por negocio). Nombre de BD = subdominio (`cliente1` → `cliente1.tuplataforma.com`).

---

## 1. Cómo montar un nuevo entorno multi-tenant

1. Railway → **New Project** (Postgres propio; no compartas el de producción).
2. Despliega este repo (Docker, puerto `8069`) y enlaza `DATABASE_URL`.
3. Variables del servicio:

```bash
ODOO_MULTI_TENANT=true
ODOO_DBFILTER=^%d$
ODOO_LIST_DB=false
ODOO_PROXY_MODE=true
DB_PASSWORD_ADMIN=<secreto-fuerte>
DB_LANGUAGE=es_ES
DB_WITH_DEMO=false
GUNICORN_WORKERS=2

# S3 compartido: objetos en <bucket>/<nombre_bd>/
ODOO_ATTACHMENT_STORAGE=s3
ORDER_BRIDGE_BANNER_S3_BUCKET=<bucket>
ORDER_BRIDGE_BANNER_S3_REGION=us-east-1
ORDER_BRIDGE_BANNER_S3_ACCESS_KEY_ID=...
ORDER_BRIDGE_BANNER_S3_SECRET_ACCESS_KEY=...
# o AWS_* como fallback
ODOO_EXTRA_INIT_MODULES=fs_attachment
```

4. Dominio: wildcard `*.tuplataforma.com` en Railway + DNS.  
   Sin wildcard aún: mapea la URL `*.up.railway.app` con `ODOO_TENANT_DOMAIN_MAP` (paso 2).
5. Redeploy. Logs esperados: `MULTI_TENANT=True` y `tenant_routing: patching http.db_filter`.
6. Comprueba: `https://<host>/web/health` → **200**.
7. Crea el primer tenant (sección 2) y define:

```bash
ODOO_TENANT_DATABASES=demo
# Solo si usas la URL Railway (sin subdominio aún):
# ODOO_TENANT_DOMAIN_MAP={"tu-servicio.up.railway.app":"demo"}
```

8. Redeploy otra vez y entra a la URL del tenant.

---

## 2. Cómo configurar un nuevo tenant

Nombre: letras/números/`_`, empieza por letra (`cliente2`). Con subdominio, el nombre **debe** coincidir (`cliente2.tuplataforma.com` → BD `cliente2`).

### Crear la BD

**UI (recomendado):** `https://<host>/tenant/provision`

- Master password = `DB_PASSWORD_ADMIN`
- Tenant = nombre de BD
- Módulos extra (opcional): `order_bridge,fs_attachment`

**CLI** (Railway shell del servicio):

```bash
./scripts/provision_tenant.sh cliente2
```

Login inicial: usuario `admin` (o `DB_USERNAME`), contraseña = `DB_PASSWORD_ADMIN` **del momento del provision**. Cambiar esa variable después **no** actualiza tenants ya creados.

### Registrar y enrutar

1. Añade el nombre a la lista (no borres los existentes):

```bash
ODOO_TENANT_DATABASES=demo,cliente2
```

2. Acceso:
   - **Subdominio** (`cliente2.tuplataforma.com`): con wildcard + `ODOO_DBFILTER=^%d$` no hace falta mapa.
   - **Dominio propio** (`tienda.com`): añádelo en Railway y en el mapa:

```bash
ODOO_TENANT_DOMAIN_MAP={"tienda.com":"cliente2"}
```

   - La URL `*.up.railway.app` solo sirve **un** tenant a la vez (vía mapa).

3. Redeploy → abre la URL → login.

### S3 (si está configurado en el entorno)

El deploy/provision crea `fs.storage` automáticamente (`s3://<bucket>/<tenant>/...`).

```bash
./scripts/verify_s3_storage.sh cliente2
# si falta el registro:
./scripts/provision_s3_storage.sh cliente2
```

Sube una imagen **nueva** de producto/banner para comprobar. Las antiguas siguen en DB hasta re-guardarlas.

### Checklist rápido

- [ ] Provision OK
- [ ] En `ODOO_TENANT_DATABASES`
- [ ] Subdominio o entrada en `ODOO_TENANT_DOMAIN_MAP`
- [ ] Redeploy + login `admin` / `DB_PASSWORD_ADMIN`
