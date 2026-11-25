# Punto 8: listado único de compras del cliente

Plan corto del ítem 8 de [`COMERCIOS.md`](COMERCIOS.md). Endpoint `GET /api/merchant_store/purchases` para que la app nueva muestre una compra con su pedido propio y sus subórdenes (incluido el caso solo comercio con `order: null`), y `merchant_name` en cada suborden sin romper apps viejas. `order_bridge` no se toca.

## Alcance

- Añadir `merchant_name` (campo nuevo, sin quitar ni renombrar nada) en `MerchantOrderSummary` (listado plano, detalle y respuesta de checkout).
- Añadir `PurchasesListQuery`, `MerchantPurchaseRow` y `MerchantPurchasesPageResponse` en `schemas/` y su serialización en `utils/serialization.py`, reutilizando `order_bridge.utils.serialization.sale_order_to_summary`.
- Añadir `GET /api/merchant_store/purchases` en `controllers/orders.py` (Bearer, misma compañía del dispositivo, 404 si Comercios está apagado):
  - Subórdenes con `order_bridge_order_id` cuelgan de ese pedido (`purchase_key = order:{id}`).
  - Subórdenes con `client_checkout_id` sin pedido enlazado forman una fila con `order: null` (`purchase_key = checkout:{client_checkout_id}`).
  - Pedidos de Tienda Apk sin subórdenes entran con `suborders: []` (`purchase_key = order:{id}`).
  - Subórdenes manuales sin checkout ni enlace forman su propia fila (`purchase_key = suborder:{id}`).
  - Orden por `date_order` descendente; `amount_total` suma pedido propio + subórdenes; paginación `limit`/`offset` sobre filas agrupadas.
- Actualizar `scripts/export_openapi.py`, regenerar `docs/openapi.json` y `static/openapi.json`, y actualizar `docs/comercios/prompt-app.md`.
- Tests en `tests/test_merchant_store_api.py` (mixta, solo comercio, solo tienda, aislamiento de partner y `merchant_name`).
- Versión `merchant_store` `19.0.1.7.0`.

## Fuera de este punto

Prueba manual (punto 9). Cambios en `order_bridge` o en la app móvil. Confirmar subórdenes, stock, facturas y cobro.

## Comprobación

- `python3 own_modules/merchant_store/scripts/export_openapi.py`
- `./own_modules/scripts/run_tests.sh merchant_store`
