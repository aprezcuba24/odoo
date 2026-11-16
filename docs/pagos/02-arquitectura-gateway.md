# 02 — Arquitectura del gateway

Plan corto del punto 2 de [`docs/PAGOS_ONLINE.md`](../PAGOS_ONLINE.md).

## Objetivo

Esqueleto Strategy / Registry / orquestador vacío en `own_modules/payment_gateway/`: interfaz que usarán PaymentIntent (punto 4) y el webhook (punto 5). Sin HTTP a Stripe, sin secretos y sin modelo de intento. `order_bridge` no se toca. No hay `providers/stripe.py`.

## Decisiones

- **Resultados neutros** en `providers/base.py`, sin tipos de Stripe:
  - `PaymentStart(external_id, sdk_payload)` — `sdk_payload` es un `dict` (en el punto 4 Stripe pondrá ahí `client_secret`).
  - `PaymentEvent(external_id, status, amount)` — `status` solo `succeeded` o `failed`.
- **`PaymentProvider` (ABC)** con dos métodos keyword-only:
  - `start_payment(*, amount, currency, reference) -> PaymentStart`
  - `parse_webhook(*, payload, signature) -> PaymentEvent`
- **Registry** en `providers/registry.py`: `ProviderRegistry` con `register(code, provider_cls)` y `get(code)` (instancia nueva). Funciones de módulo `register` / `get` delegan en un singleton. Código desconocido → `UnknownPaymentProvider`. Los tests usan una instancia local.
- **Orquestador vacío** en `services/orchestrator.py`: `PaymentOrchestrator(registry=None)` con `provider(code)`. Sin `env`, sin cobros, sin auth. Registry inyectable para tests.
- El `__init__.py` del addon no importa `providers` ni `services`. El manifiesto no cambia.

## Qué no entra

HTTP, secretos, `providers/stripe.py`, modelo de intento, controladores, escritura de `order_bridge.order.payment`, campo `code` en la vía de pago, cambios en la creación de pedidos.

## Verificación

Tras actualizar el módulo (o con el código ya cargado en tests):

1. Un proveedor falso registrado responde a `get(code)` y a `PaymentOrchestrator.provider(code)`.
2. Código desconocido lanza `UnknownPaymentProvider`.
3. Registrar dos veces el mismo código falla.
4. `PaymentProvider` no se instancia; una subclase concreta sí.
5. Tests: `./own_modules/scripts/run_tests.sh payment_gateway`.
