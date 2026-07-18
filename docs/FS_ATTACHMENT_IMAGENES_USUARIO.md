# Configurar fs_attachment: S3 solo para imágenes subidas por el usuario

Objetivo: subir a S3 solo imágenes que carga el usuario (productos, banners Tienda Apk, web/tienda), y dejar fuera archivos regenerables de la app (assets JS/CSS, etc.).

## Aprovisionamiento automático (order_bridge)

En este repo, `order_bridge.hooks.provision_media_fs_storage` (alias `provision_banner_fs_storage`) crea/actualiza el registro `fs.storage` con code `s3_order_bridge_banners` cuando hay bucket + credenciales:

| Campo | Valor |
|---|---|
| `model_xmlids` | `order_bridge.model_order_bridge_banner` |
| `field_xmlids` | Auto-descubiertos por BD: binary store + nombre contiene `image` + `registry.field.attachment=True` (Odoo 19 no tiene columna `ir.model.fields.attachment`) |
| `use_as_default_for_attachments` | `False` |
| `directory_path` (single-tenant) | `<bucket>` |
| `directory_path` (multi-tenant) | `<bucket>/{db_name}` |

**Importante:** OCA resuelve el storage desde `model_xmlids` / `field_xmlids` en `fs.storage`. Escribir solo `ir.model.storage_id` **no** basta para que los adjuntos vayan a S3.

Se ejecuta en:

- `post_init_hook` de `order_bridge`
- `docker-entrypoint.sh` → `prepare_tenant_database` (cada deploy)
- `scripts/provision_tenant.sh` (al crear/reprovisionar un tenant)

## Verificación (single-tenant y multi-tenant)

Un solo script para ambas instancias:

```bash
# Multi-tenant
./scripts/verify_s3_storage.sh cliente1

# Single-tenant (nombre de la BD de producción, p. ej. path de DATABASE_URL)
./scripts/verify_s3_storage.sh railway
```

Comprueba: modo (`ODOO_MULTI_TENANT`), `directory_path`, `model_xmlids` / `field_xmlids`, conexión S3, y adjuntos recientes (`fs_storage_code` debe ser `s3_order_bridge_banners`).

| Modo | Prefijo esperado en S3 |
|---|---|
| Single-tenant (`ODOO_MULTI_TENANT` unset) | raíz del bucket |
| Multi-tenant | `<bucket>/<db_name>/` |

Checklist:

1. `ODOO_ATTACHMENT_STORAGE=s3` + bucket (`ORDER_BRIDGE_BANNER_S3_BUCKET` o `ODOO_S3_BUCKET`) + credenciales
2. MT: `ODOO_MULTI_TENANT=true` y tenant en `ODOO_TENANT_DATABASES`
3. Subir imagen **nueva** de producto y banner; comprobar objeto en S3
4. Imágenes antiguas (pre-S3) requieren re-guardar

## Regla principal

- No activar `Use As Default For Attachments` en el storage S3.
- Asociar el storage S3 solo por `field_ids` (recomendado) o `model_ids`.

Con eso, lo que no coincida con esos campos/modelos sigue en filestore/DB de Odoo y no va al bucket.

## Cómo decide Odoo dónde guardar

`fs_attachment` resuelve en este orden:

1. Campo (`res_model` + `res_field`) configurado en `field_ids` / `field_xmlids`.
2. Modelo (`res_model`) configurado en `model_ids` / `model_xmlids`.
3. Storage marcado como default (`use_as_default_for_attachments=True`).
4. Si no hay match: fallback al storage normal de Odoo (filestore/DB según configuración).

## Configuración por UI (rápida)

1. Ir a `Ajustes -> Técnico -> FS Storage`.
2. Crear storage S3 (protocolo `s3`, `options`, `directory_path`).
3. En la sección de attachments:
   - Dejar desmarcado `Use As Default For Attachments`.
   - Añadir `field_ids` de imágenes de usuario (preferido), por ejemplo:
     - `product.field_product_template__image_1920`
     - `product.field_product_product__image_variant_1920`
   - Opcionalmente añadir `model_ids` para casos de web/tienda:
     - `product.model_product_template`
     - `product_public_category.model_product_public_category`
     - `website.model_website`

## Entidades estándar: lista completa sin omisiones

Para no dejarte ninguna entidad estándar fuera (según **tu** Odoo y módulos instalados), no conviene mantener una lista manual fija. Lo correcto es generar el inventario desde la base y usar ese resultado para `field_xmlids` / `model_xmlids`.

### Opción recomendada (automática, exacta)

Ejecuta en `odoo shell`:

```python
# Odoo 19: ir.model.fields no tiene columna searchable "attachment".
# Filtrar binary store + nombre image, luego registry.field.attachment.
Field = env["ir.model.fields"].sudo()
candidates = Field.search([
    ("ttype", "=", "binary"),
    ("store", "=", True),
    ("model_id.transient", "=", False),
    ("name", "ilike", "image"),
])
keep = Field.browse()
for irec in candidates:
    if irec.model not in env:
        continue
    mf = env[irec.model]._fields.get(irec.name)
    if mf is not None and getattr(mf, "attachment", False):
        keep |= irec

field_xmlids_map = keep.get_external_id()
field_xmlids = sorted(
    x for x in field_xmlids_map.values()
    if x and not x.startswith("__export__")
)
print("field_xmlids=" + ",".join(field_xmlids))
```

Con esto obtienes la lista completa en tu instancia (incluye estándar + custom instalados). Si quieres solo estándar, filtra por prefijos de módulos custom propios.

### Base estándar útil en eCommerce (arranque rápido)

Si quieres empezar ya, estos cubren la mayoría de imágenes de tienda/web:

- `product.field_product_template__image_1920`
- `product.field_product_product__image_variant_1920`
- `website_sale.field_product_public_category__image_1920`
- `website.field_website__logo`
- `website.field_website__favicon`
- `website_sale.field_product_image__image_1920`

Después amplía con la salida del script anterior para no dejar huecos.

## Ejemplo server_environment

Archivo de entorno (según vuestra instalación de `server_environment`), sección por código de storage:

```ini
# Ajustar ruta/nombre de fichero según server_environment del proyecto.
# Sustituir KEY/SECRET por variables de entorno o secret manager en producción.

[fs_storage.s3_images_user]
protocol=s3
options={"endpoint_url": "https://s3.eu-west-1.amazonaws.com", "key": "REPLACE_ME", "secret": "REPLACE_ME", "client_kwargs": {"region_name": "eu-west-1"}}
directory_path=mi-bucket/odoo_attachments
use_as_default_for_attachments=False
# Prioridad: campo explícito antes que modelo.
field_xmlids=product.field_product_template__image_1920,product.field_product_product__image_variant_1920
# Opcional: ampliar por modelo.
model_xmlids=website.model_website,product_public_category.model_product_public_category
base_url=https://mi-bucket-public.s3.eu-west-1.amazonaws.com
optimizes_directory_path=True
autovacuum_gc=True
```

Notas:

- `force_db_for_default_attachment_rules` no aplica si este storage no es default.
- Los XML IDs deben existir en la base (módulos instalados).
- En algunos despliegues hay que crear primero el registro `fs.storage` con el mismo `code` (`s3_images_user`) y luego dejar que `server_environment` lo complete/sobrescriba.

## Verificación mínima (producto/tienda)

1. Subir una imagen nueva de producto o banner.
2. Revisar `Ajustes -> Técnico -> Adjuntos`:
   - Debe tener `res_model`/`res_field` de imagen.
   - Debe quedar apuntando al storage S3 configurado.
3. Abrir la tienda y confirmar carga correcta de imagen.

Si una imagen no sube a S3:

- Buscar ese adjunto y revisar `res_model` + `res_field`.
- Añadir ese campo/modelo al storage.
- Repetir prueba.

## Reinicio/caché tras cambios

Después de cambiar `model_ids`/`field_ids`:

- Reiniciar Odoo (o workers) para limpiar caché de resolución.
- Volver a probar subida de una imagen nueva.

## Resumen rápido

| Objetivo | Configuración |
|---|---|
| Evitar subir assets regenerables | No usar storage default global |
| Subir solo imágenes de usuario | Configurar `field_ids`/`field_xmlids` de imágenes |
| Replicar en producción | Mismo `code` + misma config en UI o `server_environment` |

## Borrar imágenes vieja

1. Buscar `Ajustes -> Técnico -> Automatización (Acciones planificadas)`
2. Buscar `Base: limpieza automática de datos internos`
3. Pinchar el botón `Ejecutar manualmente`

De todas maneras debería ejecutarse solo