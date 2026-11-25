# Punto 2: comerciante

Plan corto del ítem 2 de [`COMERCIOS.md`](COMERCIOS.md). Modelo de comerciante con pantallas en el módulo; sin productos, subórdenes ni API.

## Alcance

- Modelo `merchant_store.merchant`: nombre, descripción, logo (`fields.Image`) y `company_id` obligatorio (nunca vacío).
- Regla multi-compañía global `company_id in company_ids`, igual que el dispositivo de Tienda Apk.
- ACL solo en grupos Usuario / Responsable Comercios (+ system).
- Lista y formulario bajo el menú raíz «Comercios»; acción sin dominio extra (la regla acota).
- Logo en el mismo S3 que las imágenes de producto (`fs.storage` `s3_order_bridge_banners` vía `field_xmlids`), bajo la subcarpeta `merchants/{merchant_id}/logo/`; sin bucket nuevo.
- Versión `19.0.1.1.0`. `order_bridge` no cambia de código.

## Fuera de este punto

`merchant_id` en producto/pedido, exclusión de catálogo, subórdenes, compra mixta, API y contrato de la app (puntos 3–8).

## Comprobación

- Crear comerciante; campos y `company_id` por defecto correctos.
- Usuario de compañía A no ve ni lee el de B; sin grupo Comercios no lee el modelo.
- Con `company_onboarding`, el menú hijo con acción queda fuera de `_visible_menu_ids` hasta activar la app.
- `_discover_image_attachment_field_xmlids` incluye `merchant_store.field_merchant_store_merchant__logo`.
- `./own_modules/scripts/run_tests.sh merchant_store`
- `./own_modules/scripts/run_tests.sh company_onboarding`
