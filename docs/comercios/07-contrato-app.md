# Punto 7: contrato para la app

Plan corto del ítem 7 de [`COMERCIOS.md`](COMERCIOS.md). Contrato OpenAPI 3.1 de `merchant_store`, endpoint de detalle de un comerciante y prompt corto para adaptar el cliente. `order_bridge` no se toca.

## Alcance

- Añadir `GET /api/merchant_store/merchants/<int:merchant_id>` en `controllers/merchants.py` (Bearer, misma compañía, 404 si no existe, archivado, otra compañía o app apagada; devuelve `MerchantRow`).
- Generador `own_modules/merchant_store/scripts/export_openapi.py` al estilo de `order_bridge`: genera `docs/openapi.json` y `static/openapi.json` sin importar `odoo-bin`.
- Controlador público `GET /api/merchant_store/openapi.json` (y `OPTIONS`) con CORS y `Cache-Control`, más `/merchant_store/static/openapi.json`.
- Prompt corto [`prompt-app.md`](prompt-app.md) para adaptar la app: carrito partido en dos llamadas, `product_id` separados, `order_bridge_order_id`, `client_checkout_id`, `store_state` independiente y endpoints de comerciantes.
- Test de paridad del OpenAPI (`test_merchant_store_openapi.py`) y tests de `GET /merchants/<id>` en `test_merchant_store_api.py`.
- Versión `merchant_store` `19.0.1.6.0`.

## Fuera de este punto

Prueba manual (punto 8). Cambios en `order_bridge` o en la app móvil. Confirmar subórdenes, stock, facturas y cobro.

## Comprobación

- `python3 own_modules/merchant_store/scripts/export_openapi.py` genera `docs/openapi.json` y `static/openapi.json` idénticos.
- `GET /api/merchant_store/merchants/<id>`: 200 del propio, 404 del archivado y 404 del de otra compañía.
- `./own_modules/scripts/run_tests.sh merchant_store`
