# Punto 6: API

Plan corto del ítem 6 de [`COMERCIOS.md`](COMERCIOS.md). Rutas HTTP bajo `/api/merchant_store/` con Bearer del dispositivo, compañía del dispositivo, Pydantic y CORS. El comerciante gana `active` (true por defecto); la API solo lista y vende los activos.

## Alcance

- Campo `active` en `merchant_store.merchant` (`Boolean`, default `True`). Archivar deja de publicarlo en la API.
- Rutas `auth='public'`, Bearer obligatorio vía decoradores de `order_bridge`. Compañía = `api_device.company_id`. Todo `sudo()` filtrado a mano por compañía y partner.
- `GET /merchants` — comerciantes activos de esa compañía.
- `GET /products` y `GET /products/<id>` — variantes activas `sale_ok` de comerciante activo de esa compañía. Query: `limit`, `offset`, `search`, `merchant_id`.
- `POST /checkouts` — `client_checkout_id`, líneas, enlace opcional a Tienda Apk. Llama a `merchant_store_checkout`. Rechaza comerciante archivado, producto propio u otra compañía. Idempotente.
- `GET /orders` y `GET /orders/<id>` — subórdenes del partner y compañía; archivar el comerciante no las esconde.
- App apagada (`company_onboarding` sin `merchant_store`): 404 en todas las rutas.
- Imágenes públicas: logo y fotos solo si el comerciante está activo.
- Versión `merchant_store` `19.0.1.5.0`. `order_bridge` no cambia de código.

## Fuera de este punto

OpenAPI y prompt de la app (punto 7). Prueba manual (punto 8). Confirmar, stock, facturas y cobro.

## Comprobación

- Sin Bearer → 401.
- Dispositivo de A solo ve y compra lo suyo; el de B no.
- Comerciante archivado fuera de listados; comprar su producto → 400; subórdenes previas siguen visibles.
- Checkout de dos comerciantes; reintento idempotente.
- Producto propio / otra compañía → 400.
- Pedido ajeno o sin comerciante → 404.
- App opcional apagada → 404.
- `./own_modules/scripts/run_tests.sh merchant_store`
