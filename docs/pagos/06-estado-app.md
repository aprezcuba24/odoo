# 06 — Estado del cobro para la app

Plan corto del punto 6 de [`docs/PAGOS_ONLINE.md`](../PAGOS_ONLINE.md).

## Objetivo

Exponer cobrado, pendiente y el estado del intento Stripe al dispositivo dueño del pedido. `client_secret` solo mientras el intento siga abierto. Sin campos nuevos en el JSON de `GET` del pedido.

## Decisiones

- **Ruta.** `GET /api/order_bridge/orders/<id>/payments/stripe` en `controllers/stripe_payment.py`, junto al POST. Mismos `auth='public'`, `csrf=False`, `@api_device_auth` y OPTIONS de CORS. Solo el dispositivo de `order_bridge_device_id`. Otro dispositivo o pedido inexistente → 404. Sin Bearer → 401.
- **Orquestador.** `PaymentOrchestrator.status_for_order(order, code='stripe')`. No llama a Stripe. Lee `order_bridge_amount_paid` y `order_bridge_amount_due` del pedido. Intento más reciente de ese pedido y `provider_code` (`id desc`), o `null`.
- **Intento abierto.** Incluye `state`, `external_id`, `amount`, `client_secret` y `publishable_key` (`provider.client_config()`). Secretos ausentes → 503.
- **Intento cerrado** (`succeeded` / `failed` / `canceled`). Mismos campos de estado sin `client_secret` ni `publishable_key`. No lee el entorno.
- **Sin intento.** 200 con `attempt: null` e importes del pedido (pendiente 0 si nadie marcó cobro pendiente ni hay líneas).

## Qué no entra

Campos en `GET /api/order_bridge/orders/<id>`, método gancho en `sale.order`, cambios en `order_bridge`, contrato de la app (punto 7), prueba manual (punto 8).

## Verificación

1. Intento `open`: cobrado 0, pendiente = total, `client_secret` y `publishable_key`.
2. Intento `succeeded` con línea de cobro: cobrado = total, pendiente 0, sin `client_secret`.
3. Intento `failed`: estado `failed`, sin secreto, pendiente = saldo.
4. Sin intento: `attempt` null.
5. Otro dispositivo 404; sin Bearer 401.
6. Tests: `./own_modules/scripts/run_tests.sh payment_gateway`.
