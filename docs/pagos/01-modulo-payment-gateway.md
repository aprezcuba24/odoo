# 01 — Módulo `payment_gateway`

Plan corto del punto 1 de [`docs/PAGOS_ONLINE.md`](../PAGOS_ONLINE.md).

## Objetivo

Crear el addon `own_modules/payment_gateway` que depende de `order_bridge` y registra la vía de pago **Stripe** sobre el modelo que ya existe (`order_bridge.payment.method`). Sin llamadas a Stripe ni cambios en la creación de pedidos.

## Decisiones

- **Localización por xmlid.** La vía se crea como `payment_gateway.payment_method_stripe`. Efectivo y transferencia ya se resuelven con `env.ref('order_bridge.payment_method_*')`; Stripe sigue el mismo patrón. No se añade el campo `code` a `order_bridge.payment.method` en este punto (el `code` del registry de proveedores es el punto 2).
- **`order_bridge` no depende de `payment_gateway`.** Instalar el gateway es `-i payment_gateway` (o Apps). El entrypoint de deploy sigue actualizando solo `base,order_bridge`.
- **Dato `noupdate="1"`.** Nombre `Stripe`, secuencia `30`, activo. Las vistas de vías de `order_bridge` ya listan el modelo; no hace falta vista nueva.

## Qué no entra

Secretos, `providers/`, orquestador, modelo de intento, endpoints HTTP, cambios en `sale.order` o en `POST /api/order_bridge/orders`. Efectivo y transferencia no se mueven.

## Verificación

Tras `-i payment_gateway`:

1. Existe `env.ref('payment_gateway.payment_method_stripe')` con nombre Stripe.
2. Siguen existiendo `order_bridge.payment_method_cash` y `order_bridge.payment_method_transfer`.
3. Un cobro con la vía Stripe en `order_bridge.order.payment` actualiza el saldo del pedido como cualquier otra vía.
4. Tests: `./own_modules/scripts/run_tests.sh payment_gateway` (módulo instalado en la BD de tests).
