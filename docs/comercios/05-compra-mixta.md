# Punto 5: compra mixta

Plan corto del ítem 5 de [`COMERCIOS.md`](COMERCIOS.md). Un checkout agrupa una `sale.order` por comerciante, con `client_checkout_id` idempotente y enlace opcional al pedido de Tienda Apk. Sin rutas HTTP.

## Alcance

- Campos en la suborden: `client_checkout_id` y `order_bridge_order_id` (Many2one a `sale.order`, sin inversa). Solo se guardan en la suborden.
- Unicidad `unique(company_id, client_checkout_id, merchant_id)`. Subórdenes manuales sin checkout siguen válidas (NULL en PostgreSQL).
- Restricciones: checkout y enlace solo con `merchant_id`; el pedido enlazado es de la misma compañía, sin comerciante y con origen `app`/`admin`; mismo partner y mismo enlace (o ninguno) dentro del checkout.
- Método `sale.order.merchant_store_checkout(...)`: agrupa líneas por comerciante, crea subórdenes en borrador sin origen, o las devuelve si el checkout ya existe. Rechaza producto sin comerciante, de otra compañía, líneas vacías o checkout vacío. No escribe el pedido de Tienda Apk.
- Lista y formulario de Comercios → Pedidos: checkout y enlace de solo lectura en la vista.
- El dominio del catálogo ya excluye `merchant_id`; no se reimplementa.
- Versión `merchant_store` `19.0.1.4.0`. `order_bridge` no cambia de código.

## Fuera de este punto

API HTTP, Bearer, Pydantic, CORS (punto 6). Contrato OpenAPI (punto 7). Prueba manual (punto 8). Confirmación, stock, facturas y cobro.

## Comprobación

- Dos comerciantes → dos subórdenes, mismo `client_checkout_id`, sin origen, borrador, Revisando.
- Misma llamada otra vez → mismas subórdenes, sin crear más.
- Producto sin comerciante, otra compañía, líneas vacías o checkout vacío rechazan.
- Con enlace, el pedido propio no cambia; estado de suborden independiente.
- Enlace inválido (otra compañía, con comerciante, sin origen) rechaza.
- `./own_modules/scripts/run_tests.sh merchant_store`
