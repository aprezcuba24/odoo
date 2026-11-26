# Adaptar la app a Comercios (`merchant_store`)

Contrato OpenAPI 3.1 de la API nueva:

- `GET /merchant_store/static/openapi.json` (o `GET /api/merchant_store/openapi.json` con CORS)
- Fichero en el repo: `own_modules/merchant_store/docs/openapi.json`

## Autenticación y compañía

- Usa el mismo header `Authorization: Bearer <device_key>` que Tienda Apk (`order_bridge`).
- Todas las rutas de `/api/merchant_store/` resuelven la compañía desde ese dispositivo. No hace falta `X-Company-Slug`.
- Si Comercios está apagado para esa compañía, las rutas responden `404` (`{"error": "not_found"}`).

## Comerciantes y catálogo

- Listado de comerciantes activos: `GET /api/merchant_store/merchants` → `{ items, total }` (`id`, `name`, `description`, `logo_url`, `logo_thumbnail_url`).
- Ficha de un comerciante: `GET /api/merchant_store/merchants/{merchant_id}`.
- Productos de comerciantes: `GET /api/merchant_store/products` (soporta `limit`, `offset`, `merchant_id`, `search`) y `GET /api/merchant_store/products/{product_id}`.
- Cada producto trae `merchant_id`. Los `product_id` de Comercios y los de Tienda Apk (`GET /api/order_bridge/products`) pertenecen a catálogos distintos y no se pueden mezclar en el mismo endpoint.

## Carrito mixto (dos llamadas)

Separa las líneas del carrito según su origen antes de confirmar:

1. **Productos propios** (de `GET /api/order_bridge/products`): envíalos a `POST /api/order_bridge/orders` como hoy. Si no hay líneas propias, no hagas esta llamada.
2. **Productos de comerciantes** (de `GET /api/merchant_store/products`): envíalos a `POST /api/merchant_store/checkouts` con:
   - `client_checkout_id`: UUID generado en la app para este checkout. Reutiliza el mismo valor en reintentos para mantener idempotencia (el servidor devuelve las subórdenes ya creadas sin duplicarlas).
   - `lines`: `[{ "product_id": ..., "qty": ... }]`. El backend parte el carrito en una suborden por comerciante.
   - `order_bridge_order_id` (opcional): si se creó el pedido propio en el paso 1, pasa aquí su `id`. Si solo hay productos de comerciantes, omítelo o manda `null`.

Si no hay líneas de comerciantes, no llames a `/api/merchant_store/checkouts`.

## Historial de órdenes

- **Historial unificado**: `GET /api/merchant_store/purchases` (soporta `limit` y `offset`). Si responde `404` porque Comercios está apagado en esa compañía, usa `GET /api/order_bridge/orders`.
  - Devuelve una lista plana ordenada por `date_order` descendente: cada fila es una orden independiente (tanto las de Tienda Apk como las de comercios), sin subórdenes anidadas.
  - Cada ítem trae `source` y `order`:
    - `source: "store"` → `order` es el resumen de Tienda Apk (`SaleOrderSummary`). Abre su detalle con `GET /api/order_bridge/orders/{id}`.
    - `source: "merchant"` → `order` es el resumen de comercio (`MerchantOrderSummary`, con `merchant_id` y `merchant_name`). Abre su detalle con `GET /api/merchant_store/orders/{id}`.
  - En ambos casos, la dirección del cliente congelada al comprar está en `order.delivery_address` (`null` si el cliente no tenía dirección al crear la orden).
- **Listado solo de órdenes de comercios**: `GET /api/merchant_store/orders` (filtro opcional `store_state`) y detalle `GET /api/merchant_store/orders/{order_id}`. También incluyen `merchant_id`, `merchant_name` y `delivery_address`.
- Cada orden de comercio tiene su propio `store_state`: `reviewing` → `negotiating` → `ready_for_delivery` → `delivered` / `canceled`, independiente del pedido propio de Tienda Apk.
- Las rutas de `/api/order_bridge/orders` permanecen sin cambios para las apps que no usan Comercios.
