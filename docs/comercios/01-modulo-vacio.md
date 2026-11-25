# Punto 1: módulo vacío `merchant_store`

Plan corto del ítem 1 de [`COMERCIOS.md`](COMERCIOS.md). Solo el esqueleto: sin comerciante, productos, subórdenes ni API.

## Alcance

- Módulo instalable `own_modules/merchant_store` con `depends: ['order_bridge']`, `application: True`, versión `19.0.1.0.0`.
- Categoría, privilegio y grupos Usuario / Responsable Comercios (mismo patrón Odoo 19 que Tienda Apk).
- `ir.model.access.csv` solo con cabecera (sin modelos).
- Menú raíz «Comercios» (`menu_merchant_store_root`), sin hijos ni acciones.
- App opcional por compañía en `company_onboarding` (`code`: `merchant_store`), apagada por defecto; el menú se oculta hasta marcar la casilla en Aplicaciones.
- `order_bridge` no cambia. El alta de compañías no recibe el grupo nuevo.

## Fuera de este punto

Comerciante, `merchant_id` en producto/pedido, compra mixta, API y contrato de la app (puntos 2–8).

## Comprobación

- Instalar el módulo; menú y grupos existen por xmlid.
- Con `company_onboarding`, el menú raíz está en la lista de menús ocultos de apps opcionales hasta activar la casilla (un root vacío sin acción no entra en `_visible_menu_ids` de Odoo hasta que el punto 2 añada pantallas).
- `./own_modules/scripts/run_tests.sh merchant_store`
- `./own_modules/scripts/run_tests.sh company_onboarding`
