# Configurar fs_attachment: S3 solo para imágenes subidas por el usuario

Objetivo: subir a S3 solo imágenes que carga el usuario (productos, web/tienda), y dejar fuera archivos regenerables de la app (assets JS/CSS, etc.).

## Regla principal

- No activar `Use As Default For Attachments` en el storage S3.
- Asociar el storage S3 solo por `field_ids` (recomendado) o `model_ids`.

Con eso, lo que no coincida con esos campos/modelos sigue en filestore/DB de Odoo y no va al bucket.

## Cómo decide Odoo dónde guardar

`fs_attachment` resuelve en este orden:

1. Campo (`res_model` + `res_field`) configurado en `field_ids`.
2. Modelo (`res_model`) configurado en `model_ids`.
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
# Campos binarios guardados como attachment (candidatos reales para fs_attachment)
Field = env["ir.model.fields"].sudo()
fields = Field.search([
    ("ttype", "=", "binary"),
    ("attachment", "=", True),
    ("store", "=", True),
    ("model_id.transient", "=", False),
])

# XML IDs de campos/modelos
field_xmlids_map = fields.get_external_id()
field_xmlids = sorted(
    x for x in field_xmlids_map.values()
    if x and not x.startswith("__export__")
)

model_recs = fields.mapped("model_id")
model_xmlids_map = model_recs.get_external_id()
model_xmlids = sorted(
    x for x in model_xmlids_map.values()
    if x and not x.startswith("__export__")
)

print("field_xmlids=" + ",".join(field_xmlids))
print("model_xmlids=" + ",".join(model_xmlids))
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