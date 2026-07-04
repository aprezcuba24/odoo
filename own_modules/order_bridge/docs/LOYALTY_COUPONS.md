# Cupones, descuentos y fidelización (Odoo 19)

Referencia para entender los programas de **Descuentos y fidelización** en Odoo 19 y su uso con **Order Bridge**. El módulo base es `loyalty`; en ventas se extiende con `sale_loyalty` (dependencia de `order_bridge`).

Menú en Odoo: **Ventas → Productos → Descuentos y fidelización**.

Documentación oficial: [Discount and loyalty programs — Odoo 19](https://www.odoo.com/documentation/19.0/applications/sales/sales/products_prices/loyalty_discount.html)

---

## Modelo mental

Todo programa (`loyalty.program`) se compone de tres piezas:

| Pieza | Modelo | Función |
|-------|--------|---------|
| **Reglas** | `loyalty.rule` | Condiciones: importe mínimo, productos, código promocional, etc. |
| **Recompensas** | `loyalty.reward` | Qué obtiene el cliente: descuento, producto gratis, envío gratis |
| **Tarjetas / cupones** | `loyalty.card` | Código único + saldo de **puntos** |

Los **puntos** son la moneda interna: las reglas los generan y las recompensas los consumen (`required_points`).

Campos clave del programa:

| Campo | Valores | Significado |
|-------|---------|-------------|
| `trigger` | `auto` / `with_code` | Se aplica solo o requiere introducir un código |
| `applies_on` | `current` / `future` / `both` | Recompensa en este pedido, en el siguiente, o acumulable en ambos |

Al introducir un código, Odoo busca primero una **regla con código** y, si no la encuentra, un **cupón** (`loyalty.card`). Si el cupón no tiene puntos suficientes, se considera ya usado.

Los tipos **Loyalty Cards** y **eWallet** no se aplican escribiendo un código: van ligados al contacto y se cargan automáticamente en el pedido.

---

## Tipos de programa

Definidos en `loyalty.program.program_type`:

| Tipo | Uso típico | ¿Código? | ¿Cuándo se usa? |
|------|------------|----------|-----------------|
| **Coupons** | Cupones únicos que generas y repartes | Sí | Pedido actual |
| **Promotions** | Descuento automático si el carrito cumple condiciones | No | Pedido actual |
| **Discount Code** | Un código fijo compartido (ej. `VERANO10`) | Sí | Pedido actual |
| **Loyalty Cards** | Puntos por compras recurrentes | No (tarjeta del cliente) | Actual y/o futuro |
| **Next Order Coupons** | Tras comprar, regalas cupón para la próxima | Auto genera cupón | Pedido **siguiente** |
| **Buy X Get Y** | Compra X unidades → créditos → producto Y gratis | No | Pedido actual |
| **Gift Card** | Tarjeta regalo con saldo en moneda | No (tarjeta nominativa) | Pedidos futuros |
| **eWallet** | Monedero digital del cliente | No | Pedidos futuros |

### Coupons

Generas cupones con el botón **Generate Coupons**. Cada uno tiene código y puntos (por defecto 1 punto = 1 recompensa). El cliente lo introduce en pedido, web, TPV o API.

### Promotions

Descuento **automático** sin código. Ejemplo por defecto de Odoo: pedido ≥ 50 € → gana 1 punto → puede canjear 10 % de descuento.

### Discount Code (`promo_code`)

Un **código fijo** en la regla (no cupones individuales). Todos los clientes usan el mismo código. Es el tipo más habitual para campañas masivas y para la API de Order Bridge.

No incluye límite «una vez por cliente»; ver [Límite de uso: ¿una vez por cliente?](#límite-de-uso-una-vez-por-cliente).

### Loyalty Cards

El cliente acumula puntos (p. ej. 1 punto por €). Puede gastarlos en el pedido actual o guardarlos (`applies_on: both`). La tarjeta va ligada al **contacto**.

### Next Order Coupons

Si el pedido cumple la regla (p. ej. ≥ 100 €), Odoo **crea un cupón** y puede enviarlo por email. Solo vale en el **próximo** pedido (`applies_on: future`).

### Buy X Get Y

Por cada unidad comprada gana **créditos** (`reward_point_mode: unit`). Con X créditos canjea un producto gratis. Ejemplo por defecto: compra 2 → gana 2 créditos → producto gratis.

### Gift Card / eWallet

Programas de **pago**, no descuentos clásicos. El cliente compra un producto «tarjeta regalo» o recarga el monedero; se crea una `loyalty.card` con saldo en moneda. En checkout se usa como forma de pago.

---

## Tipos de recompensa

En `loyalty.reward`:

| Tipo | Descripción |
|------|-------------|
| **Discount** | Porcentaje, importe fijo por pedido, o importe por punto (`discount_mode`) |
| **Free Product** | Producto gratis |
| **Free Shipping** | Requiere módulo `sale_loyalty_delivery` |

El descuento puede aplicarse al pedido entero, al producto más barato o a productos concretos.

---

## Diferencias que suelen confundir

| Pregunta | Respuesta |
|----------|-----------|
| **Coupon vs Discount Code** | Coupon = muchos códigos únicos generados; Discount Code = un código compartido en la regla |
| **Promotion vs Discount Code** | Promotion = automático; Discount Code = el cliente escribe el código |
| **Coupon vs Next Order Coupon** | Coupon = descuento **ahora**; Next Order = genera cupón **para después** |
| **Loyalty vs Coupon** | Loyalty = puntos acumulados por cliente; Coupon = código puntual que repartes |
| **Limit Usage vs una vez por cliente** | *Limit Usage* = tope **global** del programa; no limita repeticiones del mismo cliente |

---

## Límite de uso: ¿una vez por cliente?

**No**, Odoo 19 **no ofrece de serie** la opción «este Discount Code solo puede usarse una vez por cliente». El tipo **Discount Code** (`promo_code`) define un **código compartido** en la regla; cualquier contacto puede reutilizarlo en pedidos distintos mientras el programa siga activo.

### Qué hace «Limit Usage» (Limitar uso)

En el formulario del programa, **Limit Usage** + **Max usage** limitan el **número total de usos del programa entre todos los clientes**, no por persona:

| Configuración | Efecto |
|---------------|--------|
| `limit_usage = false` | Sin tope; el mismo cliente puede usar el código en muchos pedidos |
| `limit_usage = true`, `max_usage = 1` | Solo **un uso en total** (el primer cliente que lo use); el resto queda bloqueado |
| `limit_usage = true`, `max_usage = N` | Como máximo **N pedidos confirmados** con ese programa en toda la campaña |

La comprobación está en `sale_loyalty` (`program.total_order_count >= program.max_usage`). No consulta el historial por `partner_id`.

### Alternativa estándar: tipo **Coupons**

Si necesitas **un solo uso por persona** sin desarrollo custom:

1. Crea un programa tipo **Coupons** (no Discount Code).
2. Pulsa **Generate Coupons** y genera **un cupón por cliente**, con **1 punto** y el **contacto** asignado (`partner_id`).
3. Cada cupón tiene **código único**; al canjearlo en un pedido confirmado, los puntos pasan a 0 y deja de ser válido.
4. Si el cupón tiene `partner_id`, otro contacto no puede usarlo.

**Inconveniente:** no es un único código tipo `BIENVENIDA10` para todos; hay que generar y repartir cupones individuales (email, app, etc.).

### Discount Code + Order Bridge hoy

La API acepta `promo_code` y delega en `_try_apply_code()` de Odoo. **No hay comprobación extra** de «este teléfono/cliente ya usó este código». Un mismo `res.partner` puede aplicar `VERANO10` en varios pedidos vía API.

Para un código compartido con límite **una vez por cliente** haría falta **desarrollo custom** (p. ej. comprobar pedidos confirmados con el mismo `partner_id` y `order_bridge_promo_code` antes de aplicar el descuento).

Referencias del foro Odoo: [once per customer](https://www.odoo.com/forum/help-1/how-to-create-a-promo-code-that-each-customer-can-only-use-once-203511), [new users once](https://www.odoo.com/forum/help-1/promo-codediscount-code-for-all-new-users-once-per-new-users-233753).

---

## Flujo simplificado

```
Pedido / carrito
    │
    ├─ ¿Código introducido?
    │       ├─ Sí → buscar regla o cupón (loyalty.card)
    │       └─ No → evaluar programas con trigger=auto
    │
    ├─ ¿Cumple reglas? (importe, productos, fechas, límite de usos…)
    │       └─ Sí → sumar puntos
    │
    └─ ¿Puntos ≥ recompensa?
            ├─ Sí → aplicar recompensa (línea de descuento en el pedido)
            └─ No → guardar puntos en tarjeta/cupón para después
```

En un presupuesto de ventas: botón **Recompensa** o campo de código promocional.

---

## Integración con Order Bridge

`order_bridge` depende de `sale_loyalty`. Al crear un pedido por API se puede enviar un código promocional:

```json
POST /api/order_bridge/orders
{
  "client_order_id": "…",
  "lines": […],
  "promo_code": "VERANO10"
}
```

Comportamiento:

1. Si `promo_code` está presente, se llama a `sale.order._try_apply_code()` y se aplica **una única recompensa** (`_apply_program_reward`).
2. Si el código es inválido, la petición responde **400** y **no se crea** el pedido.
3. Si el código tiene **varias recompensas** posibles, la API rechaza el pedido (no soporta elegir entre varias).
4. Los reintentos con el mismo `client_order_id` son idempotentes: el `promo_code` del reintero se **ignora** si el pedido ya existía.
5. La respuesta incluye `promo_code` y `discount_amount` cuando hubo descuento.

Tipos recomendados para la API:

- **Discount Code** (`promo_code`): un código fijo, una recompensa clara.
- **Coupons**: códigos únicos generados; también funcionan si el cupón tiene una sola recompensa.

No aplicables vía `promo_code` en la API:

- **Promotions** (automáticas): no llevan código; requieren lógica distinta en el flujo de pedido.
- **Loyalty Cards / eWallet**: van ligados al contacto, no a un código en el body.

Ver también: [ARCHITECTURE.md](./ARCHITECTURE.md) (sección de cupones) y [API_EXAMPLES.md](./API_EXAMPLES.md).

---

## Referencias

- [Discount and loyalty programs — Odoo 19](https://www.odoo.com/documentation/19.0/applications/sales/sales/products_prices/loyalty_discount.html) — configuración paso a paso, reglas, recompensas, límites de uso
- [Odoo 19 loyalty programs (referencia técnica)](https://octurasolutions.com/resources/odoo-19-loyalty-programs-points-gift-cards-and-coupons-for-ecommerce-and-pos) — modelos Python y ejemplos de configuración
- Código fuente en este repositorio: `addons/loyalty/`, `addons/sale_loyalty/`
