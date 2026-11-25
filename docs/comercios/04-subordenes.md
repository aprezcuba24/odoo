# Punto 4: subórdenes

Plan corto del ítem 4 de [`COMERCIOS.md`](COMERCIOS.md). Una `sale.order` por comerciante, sin `order_bridge_origin`, con el estado de tienda que ya existe; pantallas solo en el módulo; fuera de Ventas y de los reportes. Sin confirmar ni API.

## Alcance

- Campo `merchant_id` en `sale.order` (`merchant_store.merchant`, `check_company=True`, `ondelete='restrict'`).
- Al guardar con comerciante: `company_id` = compañía del comerciante, `order_bridge_origin` vacío, estado Odoo en borrador.
- Estado de tienda (`order_bridge_store_state`) con las mismas transiciones que Tienda Apk; válido también sin origen cuando hay `merchant_id`.
- `action_confirm` rechaza órdenes con comerciante. Las líneas deben coincidir en comerciante con la orden (y al revés).
- Lista y formulario bajo **Comercios → Pedidos**; dominio `merchant_id` definido.
- Dominio `merchant_id` vacío en Pedidos y Presupuestos de Ventas.
- Reportes: `sale.report` y SQL de `bi_analytics` excluyen `merchant_id`. `merchant_store` depende de `bi_analytics`.
- Versión `merchant_store` `19.0.1.3.0`. `bi_analytics` `19.0.1.1.0`. `order_bridge` no cambia de código.

## Fuera de este punto

`client_checkout_id`, enlace al pedido de Tienda Apk, API, contrato de la app y prueba manual (puntos 5–8). Confirmación, stock, facturas y cobro.

## Comprobación

- Crear suborden; comerciante, compañía, sin origen, borrador, Revisando.
- Transiciones de estado de tienda válidas e inválidas; el pedido propio no cambia.
- `action_confirm` rechaza; líneas cruzadas rechazan.
- Acciones de Ventas y Tienda Apk las dejan fuera; Comercios las lista.
- `sale.report` y `bi.product.sale.report` (con estado forzado a `sale`) omiten `merchant_id`.
- `./own_modules/scripts/run_tests.sh merchant_store`
- `./own_modules/scripts/run_tests.sh bi_analytics`
