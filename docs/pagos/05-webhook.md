# 05 — Webhook firmado de Stripe

Plan corto del punto 5 de [`docs/PAGOS_ONLINE.md`](../PAGOS_ONLINE.md).

## Objetivo

Recibir el webhook de Stripe, verificar la firma sobre el cuerpo crudo y, si el PaymentIntent se confirma, escribir una sola línea `order_bridge.order.payment` con la vía Stripe. Un intento fallido actualiza el estado y no crea cobro. Sin endpoint de estado para la app.

## Decisiones

- **Ruta.** `POST /api/payment_gateway/stripe/webhook` en `controllers/stripe_payment.py`. `auth='public'`, `csrf=False`, sin Bearer. Cuerpo crudo (`get_data()`) y cabecera `Stripe-Signature`. Firma inválida → 400. `STRIPE_WEBHOOK_SECRET` ausente → 503. Evento que no es de PaymentIntent → 200 sin escribir nada.
- **Secreto.** `stripe_webhook_secret()` en `services/secrets.py`. Ya documentado en `.env.example`.
- **Adaptador.** `parse_webhook` con `stripe.Webhook.construct_event` (verificador inyectable). `payment_intent.succeeded` → `succeeded`; `payment_intent.payment_failed` → `failed`; otro tipo → evento ignorado. `external_id` = id del PaymentIntent; `amount` en unidades mayores vía `from_stripe_minor_units`.
- **Orquestador.** `apply_webhook_event(event)`:
  - Intento por `external_id`; si no existe → 404 (Stripe reintenta).
  - `FOR UPDATE` de la fila del intento.
  - **succeeded:** ya `succeeded` → sin otra línea. `canceled` → sin línea. `open`/`failed` con importe distinto → 400. Importe igual → una línea con `payment_gateway.payment_method_stripe` y estado `succeeded`.
  - **failed:** solo si `open` → `failed`. Nunca crea cobro. No degrada `succeeded` ni `canceled`.
- **Idempotencia.** Línea y estado en la misma transacción; el reintento ve `succeeded` y no inserta otra fila. Sin campo nuevo en `order_bridge`.

## Qué no entra

Endpoint de estado (punto 6), contrato de la app (punto 7), prueba manual (punto 8), reembolsos, `payment_intent.canceled` como cobro, cambios en `order_bridge`.

## Verificación

1. Firma válida + `succeeded` → una línea Stripe y intento `succeeded`.
2. Reintento del mismo evento → 200 sin segunda línea.
3. `payment_failed` → intento `failed`, sin cobro.
4. Firma inválida → 400; secreto ausente → 503; intento desconocido → 404.
5. Tests: `./own_modules/scripts/run_tests.sh payment_gateway`.
