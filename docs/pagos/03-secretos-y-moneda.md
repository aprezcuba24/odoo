# 03 — Secretos y moneda

Plan corto del punto 3 de [`docs/PAGOS_ONLINE.md`](../PAGOS_ONLINE.md).

## Objetivo

Documentar las tres variables de entorno de prueba de Stripe y una comprobación local de que la moneda del pedido es una divisa de presentment que Stripe puede cobrar. Sin PaymentIntent, sin webhook y sin llamadas HTTP. Aún no se cobra.

## Decisiones

- **Solo documentación de secretos.** En [`.env.example`](../../.env.example), bloque con placeholders de test (`sk_test_`, `pk_test_`, `whsec_`) para:
  - `STRIPE_SECRET_KEY`
  - `STRIPE_PUBLISHABLE_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  Sin lector en Python en este punto. Sin SDK `stripe` ni dependencia nueva.
- **Lista local, sin HTTP.** `own_modules/payment_gateway/services/currency.py` con un `frozenset` de códigos ISO 4217 en minúsculas (divisas de presentment de Stripe). `assert_stripe_currency(code)` normaliza (`USD` → `usd`) y lanza `UnsupportedStripeCurrency` si el código está vacío o no está en la lista (p. ej. `cup`).
- **Entrada: el código de `sale.order.currency_id`.** `order_currency_code(order)` devuelve `order.currency_id.name`. Pedido sin moneda → rechazo. No se consulta la cuenta de Stripe (si la cuenta no tiene esa divisa habilitada, el error llegará al crear el intent en el punto 4).
- **El orquestador no cambia.** La comprobación es una función suelta que el punto 4 llamará antes de `start_payment`.
- **`order_bridge` y el manifiesto no se tocan.**

## Qué no entra

PaymentIntent, modelo de intento, **Queda por cobrar**, webhook, lectura de las claves, conversión a unidades menores, endpoints HTTP y `providers/stripe.py`.

## Verificación

1. `assert_stripe_currency('USD')` y `'eur'` pasan; `'CUP'`, `''` y un código desconocido lanzan `UnsupportedStripeCurrency`.
2. Un `sale.order` con moneda de la compañía (USD en esta base) pasa; uno con moneda forzada a un código no listado falla.
3. `.env.example` contiene las tres variables y ningún secreto real.
4. Tests: `./own_modules/scripts/run_tests.sh payment_gateway`.
