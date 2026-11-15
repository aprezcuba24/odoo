# 03 — Secretos y moneda

Plan corto del punto 3 de [`docs/PAGOS_ONLINE.md`](../PAGOS_ONLINE.md).

## Objetivo

Documentar dónde viven las tres claves de prueba de Stripe y una comprobación local de que la moneda del pedido es una divisa de presentment que Stripe puede cobrar. Sin PaymentIntent, sin webhook y sin llamadas HTTP. Aún no se cobra.

## Decisiones

- **Siempre en base de datos.** Modelo `payment_gateway.stripe.account` (`company_id` único, `secret_key`, `publishable_key`, `webhook_secret`). Las claves se configuran en Tienda Apk → Configuración → Stripe; solo el Administrador (`base.group_system`) tiene acceso. No hay variables de entorno Stripe ni fallback a `os.environ`.
- **Resolución.** `credentials_for_company(env, company)` en `own_modules/payment_gateway/services/secrets.py`: fila completa de esa compañía; si falta o está incompleta → `MissingStripeSecrets`.
- **Webhook.** `POST /api/payment_gateway/stripe/webhook` usa `base.main_company`. `POST /api/payment_gateway/stripe/webhook/<order_bridge_slug>` usa la compañía del slug. En ambos casos el secreto sale de la fila de esa compañía; el intento debe pertenecer a ella cuando hay slug.
- **Lista local, sin HTTP.** `own_modules/payment_gateway/services/currency.py` con un `frozenset` de códigos ISO 4217 en minúsculas (divisas de presentment de Stripe). `assert_stripe_currency(code)` normaliza (`USD` → `usd`) y lanza `UnsupportedStripeCurrency` si el código está vacío o no está en la lista (p. ej. `cup`).
- **Entrada: el código de `sale.order.currency_id`.** `order_currency_code(order)` devuelve `order.currency_id.name`. Pedido sin moneda → rechazo. No se consulta la cuenta de Stripe (si la cuenta no tiene esa divisa habilitada, el error llegará al crear el intent en el punto 4).
- **`order_bridge` no declara dependencia del gateway.** Las claves viven en `payment_gateway`, no en `order_bridge.general_settings`.

## Qué no entra

PaymentIntent (punto 4), modelo de intento, **Queda por cobrar**, conversión a unidades menores, endpoints HTTP de cobro y la pantalla del cliente. El webhook firmado es el punto 5.

## Verificación

1. `assert_stripe_currency('USD')` y `'eur'` pasan; `'CUP'`, `''` y un código desconocido lanzan `UnsupportedStripeCurrency`.
2. Un `sale.order` con moneda de la compañía (USD en esta base) pasa; uno con moneda forzada a un código no listado falla.
3. Sin fila Stripe (o incompleta) → `MissingStripeSecrets`, aunque existan variables `STRIPE_*` en el entorno.
4. Dos compañías con claves distintas; el POST de un pedido de A usa la clave de A; el webhook `/webhook/<slug-b>` acepta la firma de B y rechaza la de A.
5. Tests: `./own_modules/scripts/run_tests.sh payment_gateway`.
