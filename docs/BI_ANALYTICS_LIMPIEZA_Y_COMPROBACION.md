# Inteligencia de Negocio (`bi_analytics`) — limpieza y comprobación manual

Guía para dejar los informes en cero (o con datos controlados) y verificar el módulo de punta a punta.

## Qué datos alimentan los informes

| Origen | Modelo | Solo se cuentan si… |
|--------|--------|---------------------|
| Pedidos de venta | `sale.order` / `sale.order.line` | `state = 'sale'` (confirmado) |
| Órdenes TPV | `pos.order` / `pos.order.line` | `state IN ('paid', 'done')` |
| Gastos | `bi.other.cost` | `state = 'confirmed'` |
| Entradas de insumos | `bi.supply.entry` | Existen (afectan stock y costo promedio) |
| Insumos | `bi.supply` | Catálogo (no aparecen solos en IPV, pero sí en gastos de tipo insumo) |

Los reportes SQL (`bi.profitability.report`, `bi.product.sale.report`, `bi.other.cost.report`) y el IPV (`bi.profitability.summary`) son vistas / transientes: **no se borran**; se vacían al dejar de cumplir esos filtros.

Categorías (`bi.cost.category`) son configuración (Costo fijo, Insumo, Otro). No hace falta borrarlas.

---

## 1. Limpiar datos desde shell de Odoo

Abre el shell contra tu base (ajusta host/usuario/contraseña si hace falta):

```bash
python3 odoo-bin shell -d NOMBRE_BD --no-http
```

### 1.1 Excluir ventas (sin borrar pedidos)

Los informes **solo** incluyen pedidos en estado `sale`. Cualquier otro estado los saca del cálculo.

Opción recomendada: **cancelar** pedidos confirmados:

```python
# Pedidos de venta confirmados → cancelados (dejan de contar en BI)
SaleOrder = env['sale.order']
orders = SaleOrder.search([('state', '=', 'sale')])
print(f'Pedidos a cancelar: {len(orders)}')
orders.action_cancel()
env.cr.commit()
```

Si `action_cancel()` falla en algún pedido (facturado, etc.), fuerza el estado solo para pruebas:

```python
# SOLO entornos de prueba: fuerza estado cancel
orders = env['sale.order'].search([('state', '=', 'sale')])
orders.write({'state': 'cancel'})
env.cr.commit()
```

Estados que **no** cuentan: `draft`, `sent`, `cancel`. El que **sí** cuenta: `sale`.

### 1.2 Excluir órdenes TPV (obligatorio por SQL)

Los informes solo incluyen TPV en `paid` o `done`.

**Importante:** en Odoo 19, `pos.order.write({'state': 'cancel'})` **falla** si la orden ya está pagada/posteada (`UserError: This order has already been paid...`). `action_pos_order_cancel()` solo cancela borradores. Para pruebas hay que forzar el estado por SQL:

```python
# Diagnóstico
env.cr.execute("""
    SELECT state, COUNT(*) FROM pos_order
    GROUP BY state ORDER BY state
""")
print('Estados TPV antes:', env.cr.fetchall())

# Forzar cancelación (solo bases de prueba)
env.cr.execute("""
    UPDATE pos_order
       SET state = 'cancel'
     WHERE state IN ('paid', 'done')
""")
print(f'TPV actualizadas: {env.cr.rowcount}')
env.cr.commit()

# Invalidar caché ORM
env['pos.order'].invalidate_model(['state'])

env.cr.execute("""
    SELECT state, COUNT(*) FROM pos_order
    GROUP BY state ORDER BY state
""")
print('Estados TPV después:', env.cr.fetchall())
```

Tras esto, `search([('state', 'in', ('paid', 'done'))])` debe devolver 0. Recarga el menú BI (o F5).

### 1.3 Limpiar gastos del módulo

Los gastos en borrador **no** entran en IPV ni en “Reportes de gastos”. Puedes devolverlos a borrador o borrarlos.

```python
OtherCost = env['bi.other.cost']

# Opción A: devolver confirmados a borrador (siguen en Registro → Gastos, pero no en informes)
confirmed = OtherCost.search([('state', '=', 'confirmed')])
print(f'Gastos confirmados → borrador: {len(confirmed)}')
confirmed.action_draft()

# Opción B: borrar todos los gastos
all_costs = OtherCost.search([])
print(f'Gastos a borrar: {len(all_costs)}')
all_costs.unlink()

env.cr.commit()
```

### 1.4 Limpiar insumos y entradas

```python
# Primero entradas, luego insumos (las entradas se cascadian al borrar el insumo,
# pero conviene vaciar métricas de forma explícita)
entries = env['bi.supply.entry'].search([])
print(f'Entradas a borrar: {len(entries)}')
entries.unlink()

supplies = env['bi.supply'].search([])
print(f'Insumos a borrar: {len(supplies)}')
supplies.unlink()

env.cr.commit()
```

### 1.5 Script completo (todo de una vez)

Copia y pega en el shell de Odoo. Ajusta flags según lo que quieras conservar.

```python
"""
Limpia / excluye datos que alimentan bi_analytics.
Ejecutar solo en bases de prueba o con backup.

NOTA TPV: no uses write({'state': 'cancel'}) en órdenes paid/done;
Odoo lo bloquea. Se fuerza por SQL.
"""
CANCEL_SALES = True          # Cancela sale.order en state=sale
CANCEL_POS = True            # Cancela pos.order paid/done vía SQL
DELETE_OTHER_COSTS = True    # True = unlink; False = action_draft
DELETE_SUPPLIES = True       # Entradas + insumos

if CANCEL_SALES:
    sale_orders = env['sale.order'].search([('state', '=', 'sale')])
    print(f'[venta] Cancelando {len(sale_orders)} pedidos…')
    try:
        sale_orders.action_cancel()
    except Exception as e:
        print(f'  action_cancel falló ({e}); forzando state=cancel')
        sale_orders.write({'state': 'cancel'})

if CANCEL_POS:
    env.cr.execute("""
        SELECT state, COUNT(*) FROM pos_order
        GROUP BY state ORDER BY state
    """)
    print('[tpv] Antes:', env.cr.fetchall())
    env.cr.execute("""
        UPDATE pos_order
           SET state = 'cancel'
         WHERE state IN ('paid', 'done')
    """)
    print(f'[tpv] Filas actualizadas: {env.cr.rowcount}')
    env['pos.order'].invalidate_model(['state'])
    env.cr.execute("""
        SELECT state, COUNT(*) FROM pos_order
        GROUP BY state ORDER BY state
    """)
    print('[tpv] Después:', env.cr.fetchall())

if DELETE_OTHER_COSTS:
    costs = env['bi.other.cost'].search([])
    print(f'[gastos] Borrando {len(costs)} registros…')
    costs.unlink()
else:
    confirmed = env['bi.other.cost'].search([('state', '=', 'confirmed')])
    print(f'[gastos] Devolviendo {len(confirmed)} a borrador…')
    confirmed.action_draft()

if DELETE_SUPPLIES:
    entries = env['bi.supply.entry'].search([])
    print(f'[insumos] Borrando {len(entries)} entradas…')
    entries.unlink()
    supplies = env['bi.supply'].search([])
    print(f'[insumos] Borrando {len(supplies)} insumos…')
    supplies.unlink()

env.cr.commit()

# Verificación inmediata
pos_left = env['pos.order'].search_count([('state', 'in', ('paid', 'done'))])
sale_left = env['sale.order'].search_count([('state', '=', 'sale')])
prod_rows = env['bi.product.sale.report'].search_count([])
print(f'Quedan SO confirmados: {sale_left}')
print(f'Quedan TPV paid/done: {pos_left}')
print(f'Filas reporte productos: {prod_rows}')
print('Listo. Recarga los menús de Inteligencia de Negocio (F5).')
```

### 1.6 Comprobar que los informes quedaron vacíos

```python
print('SO confirmados:', env['sale.order'].search_count([('state', '=', 'sale')]))
print('TPV paid/done:', env['pos.order'].search_count([('state', 'in', ('paid', 'done'))]))
print('Ventas producto:', env['bi.product.sale.report'].search_count([]))
print('Gastos informe:', env['bi.other.cost.report'].search_count([]))
rows = env['bi.profitability.report'].search([])
print('Filas IPV con venta/costo > 0:',
      len(rows.filtered(lambda r: r.sale_amount or r.product_cost_amount or r.other_cost_amount)))
```

Tras cancelar ventas/TPV y vaciar gastos, esos contadores deben ser `0` (o filas IPV sin importes). Si `TPV paid/done` sigue > 0, vuelve a ejecutar el `UPDATE` de la sección 1.2.

---

## 2. Comprobación manual completa

Hazla con un usuario del grupo **Usuario / Responsable de Ventas** (`sales_team.group_sale_salesman`). Las categorías de costo solo las edita un **Responsable de Ventas** (`group_sale_manager`).

Usa fechas de **hoy** (o un día concreto del mes actual) y anota importes esperados antes de abrir IPV.

### Paso 0 — Preparación

1. Instala/actualiza el módulo: Aplicaciones → Inteligencia de Negocio → Actualizar (o `-u bi_analytics`).
2. Confirma que aparece el menú **Inteligencia de Negocio** con:
   - Informes → Reportes de productos, Reportes de gastos, IPV
   - Registro → Gastos, Entrada de insumos
   - Configuración → Categoría, Insumos
3. En Configuración → Categoría deben existir al menos: **Costo fijo**, **Insumo**, **Otro**.
4. (Opcional) Ejecuta antes el script de limpieza de la sección 1 para partir de cero.

### Paso 1 — Catálogo de insumos

1. **Configuración → Insumos → Nuevo**
   - Nombre: `Harina test`
   - Unidad: `kg`
2. Guarda. Stock disponible y costo promedio deben ser `0`.

### Paso 2 — Entrada de insumos

1. **Registro → Entrada de insumos → Nuevo**
   - Insumo: `Harina test`
   - Fecha: hoy
   - Cantidad: `10`
   - Precio de costo: `5` (total implícito 50)
2. Guarda.
3. Abre el insumo: **Stock disponible = 10**, **Costo promedio = 5**.
4. Crea una segunda entrada: cantidad `10`, precio `7`.
5. Verifica costo promedio ponderado: `(10×5 + 10×7) / 20 = 6`. Stock = `20`.

### Paso 3 — Gastos (fijo, otro, insumo)

1. **Registro → Gastos → Nuevo** (costo fijo)
   - Categoría: Costo fijo
   - Descripción: `Alquiler test`
   - Importe: `100`
   - Fecha: hoy
   - Estado inicial: Borrador → pulsa **Confirmar**
2. Nuevo gasto (otro)
   - Categoría: Otro
   - Descripción: `Varios test`
   - Importe: `25`
   - Confirmar
3. Nuevo gasto (insumo)
   - Categoría: Insumo
   - Insumo: `Harina test`
   - Cantidad: `4`
   - La descripción y el importe deben autocompletarse (≈ `4 × 6 = 24`)
   - Confirmar → el stock del insumo debe bajar a `16`
4. Comprueba validaciones:
   - Gasto insumo con cantidad `0` → error
   - Gasto insumo con cantidad mayor al stock → error al confirmar
   - Gasto fijo con importe `0` → error
5. **Devolver a borrador** un gasto de insumo y verifica que el stock se recupera.

### Paso 4 — Venta (pedido de venta)

1. Crea un producto vendible con precio lista `10` y costo (`standard_price` / margen) `4`.
2. Crea un **pedido de venta**, confirma (`state = sale`).
   - Línea: cantidad `5`, precio `10` → venta `50`, costo producto `20` (si `purchase_price` = 4).
3. Deja otro pedido en **borrador** o **cancelado**: no debe aparecer en informes.

### Paso 5 — Venta TPV (si usas Point of Sale)

1. Abre una sesión TPV y cobra una orden con el mismo producto (o uno TPV), p. ej. qty `2`, subtotal `20`, costo conocido.
2. Confirma que la orden queda en `paid` o `done`.
3. Si el producto también vino de un pedido de venta enlazado al TPV, el módulo evita duplicar líneas con `sale_order_line_id` (no deben sumarse dos veces).

### Paso 6 — Reportes de productos

1. **Informes → Reportes de productos**
2. Filtra por fecha de hoy / este mes.
3. Debe aparecer el producto con:
   - Cantidad y venta del pedido confirmado (+ TPV si aplica)
   - Costo y ganancia coherentes
4. Pedidos cancelados / borrador: **no** deben listarse.
5. Agrupa por producto / categoría y comprueba totales.

### Paso 7 — Reportes de gastos

1. **Informes → Reportes de gastos**
2. Solo gastos **confirmados**.
3. Verifica importes de alquiler, varios e insumo.
4. Un gasto en borrador **no** debe salir.
5. Prueba filtros por categoría / tipo / fecha.

### Paso 8 — IPV (resumen de rentabilidad)

1. **Informes → IPV**
2. Periodo = mes actual (botones Mes anterior / Mes siguiente).
3. Pestaña **Detalle**: una fila por día con ventas, costo de productos y margen bruto.
4. Pestaña **Indicadores**:
   - Ventas = suma ventas del periodo (SO + TPV)
   - Costo de productos = suma costos de líneas
   - Otros costos = gastos confirmados del periodo
   - Costo total = costo productos + otros costos
   - Utilidad = ventas − costo total
   - % : costo por peso de venta, índice de costo total, % ganancia
5. Cambia el rango de fechas: los totales deben recalcularse al vuelo.
6. Cancela el pedido de venta (`action_cancel` o estado distinto de `sale`): al recargar IPV, esas ventas deben desaparecer.
7. Devuelve un gasto a borrador: “Otros costos” debe bajar.

### Paso 9 — Multi-compañía (si aplica)

1. Crea datos en otra compañía.
2. En IPV / listados, filtra por compañía: no deben mezclarse importes.

### Paso 10 — Permisos

1. Usuario vendedor: puede ver informes, gastos, insumos y entradas; **no** debería administrar categorías (solo manager).
2. Usuario sin grupo de ventas: no ve el menú.

### Paso 11 — Zona horaria

1. Los pedidos usan `date_order` (UTC) convertida a la zona del usuario para el día del IPV.
2. Crea un pedido cerca de medianoche y comprueba que cae en el día esperado según tu TZ (Preferencias de usuario).

### Paso 12 — Cierre

1. Vuelve a ejecutar el script de limpieza (sección 1) si quieres dejar la BD limpia.
2. Confirma contadores de la sección 1.6 en cero.

---

## 3. Referencia rápida de estados

| Documento | Cuenta en BI | No cuenta |
|-----------|--------------|-----------|
| `sale.order` | `sale` | `draft`, `sent`, `cancel`, … |
| `pos.order` | `paid`, `done` | `draft`, `cancel`, `invoiced`*, … |
| `bi.other.cost` | `confirmed` | `draft` |

\*Comprueba en tu base qué estados TPV existen; el filtro del módulo es explícitamente `paid` y `done`.

---

## 4. Tests automáticos (opcional)

```bash
python3 odoo-bin -d NOMBRE_BD -i bi_analytics --test-enable --stop-after-init --no-http
# o solo el módulo ya instalado:
python3 odoo-bin -d NOMBRE_BD --test-tags=bi_analytics --stop-after-init --no-http
```

No sustituyen la comprobación manual de UI (menús, botones, onchange, stock visible).
