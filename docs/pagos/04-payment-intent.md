# 04 — PaymentIntent de un pedido ya creado

Plan corto del punto 4 de [`docs/PAGOS_ONLINE.md`](../PAGOS_ONLINE.md).

## Objetivo

Abrir un PaymentIntent Stripe por el saldo de un pedido ya creado. Endpoint autenticado con el dispositivo del pedido; respuesta con `client_secret` y clave publicable; el pedido queda **Queda por cobrar**. Sin webhook y sin línea de cobro.

## Decisiones

- **Ruta.** `POST /api/order_bridge/orders/<id>/payments/stripe` en `payment_gateway` (`controllers/stripe_payment.py`), auth `api_device_auth` de `order_bridge`. Solo el dispositivo de `order_bridge_device_id`. Otro dispositivo o pedido inexistente → 404. Pedido cancelado → 400. Cuerpo vacío; el importe lo calcula el servidor.
- **Importe.** `amount_total` menos suma de `order_bridge.order.payment`. Si el saldo ≤ 0 → 400, sin llamar a Stripe. No se escribe cobro en este punto.
- **Queda por cobrar.** Tras guardar el intento, `order_bridge_payment_pending = True` en ese pedido.
- **Modelo `payment_gateway.payment.attempt`.** Pedido, `provider_code`, `external_id` (único), `client_secret` (grupos: system), estado `open` / `succeeded` / `failed` / `canceled`, importe y moneda. Sin vista. ACL lectura ventas, escritura manager.
- **Un intento abierto por pedido.** Mismo importe → reutilizar. Importe distinto → cancelar el PaymentIntent anterior y abrir otro. Bloqueo `FOR UPDATE` de la fila del pedido.
- **Adaptador Stripe.** `providers/stripe.py` implementa `start_payment`, registra `stripe`. `parse_webhook` aún no (punto 5). `cancel_payment` solo en Stripe. Cliente HTTP inyectable. Claves `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` desde el entorno. Dependencia `stripe` en requirements y manifiesto. Unidades menores en `to_stripe_minor_units`.
- **Orquestador.** `PaymentOrchestrator.start_for_order(order, code='stripe')` concentra moneda, saldo, reutilización/cancelación, alta del intento y la marca de pendiente.
- **`order_bridge` no se modifica.**

## Qué no entra

Webhook, línea `order_bridge.order.payment`, endpoint de estado para la app, campos en el JSON de `GET` del pedido, lectura de `STRIPE_WEBHOOK_SECRET`.

## Verificación

1. Pedido sin cobros: intento `open`, pendiente marcado, respuesta con `client_secret` y `publishable_key`.
2. Segundo POST con el mismo saldo no crea otro intento.
3. Cobros que cubren el total: rechazo; sin marca de pendiente.
4. Cobro parcial: intent por el resto.
5. Otro dispositivo 404; sin Bearer 401; moneda no admitida / pedido cancelado 400.
6. Tests: `./own_modules/scripts/run_tests.sh payment_gateway`.
