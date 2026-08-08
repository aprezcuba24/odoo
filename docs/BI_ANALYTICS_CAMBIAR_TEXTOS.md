# Guía: Cambiar textos en el módulo `bi_analytics` (Inteligencia de Negocio)

> Ubicación del módulo: `own_modules/bi_analytics/`

## Qué hace este módulo

Proporciona los reportes de inteligencia de negocio:

- **IPV** (antes "Reportes de productos"): reporte de ventas por producto.
- **Estado de resultados** (antes "IPV"): resumen mensual de rentabilidad con indicadores.
- Gastos, insumos y categorías de costo.

## Dónde viven los textos

Los textos que ve el usuario se definen en tres capas distintas:

### 1. Etiquetas de campos — `models/*.py`

El atributo `string=` de cada campo. Ejemplo (`models/product_sale_report.py`):

```python
qty_sold = fields.Float(string='Ventas', readonly=True)               # Cantidad vendida
sale_amount = fields.Monetary(string='Importe de venta', readonly=True)
cost_amount = fields.Monetary(string='Costo de venta', readonly=True)
profit_amount = fields.Monetary(string='Ganancia', readonly=True)
```

Modelos que tienen etiquetas de campos:

- `models/product_sale_report.py` — reporte IPV (cantidad/ventas, importe de venta, costo de venta, ganancia).
- `models/profitability_report.py` — resumen diario de rentabilidad.
- `models/profitability_summary.py` — resumen del **Estado de resultados** (indicadores: otros gastos, gasto total, gasto por peso de venta, índice de gasto total, % ganancia, ganancia).
- `models/other_cost.py`, `models/other_cost_report.py`, `models/supply.py`, `models/supply_entry.py`, `models/cost_category.py` — gastos, insumos y categorías.

### 2. Títulos de vistas, acciones y menús (`views/*.xml`)

- `views/product_sale_report_views.xml` — lista/búsqueda y acción del **IPV** (`string="IPV"`).
- `views/profitability_report_views.xml` — lista y form del **Estado de resultados** (`string="Estado de resultados"`), resúmenes de columnas (`sum="Total ganancia"`), páginas y grupos.
- `views/bi_analytics_menu.xml` — textos de los menús (`<menuitem name="...">`).
- El resto de `views/*.xml` — gastos, insumos, categorías de costo, entradas.

### 3. Traducciones (`i18n/*.po`)

- `i18n/es.po` (español) y `i18n/es_419.po` (español latinoamericano).
- En este módulo las cadenas fuente (Python/XML) ya están en español, por lo que `msgid` y `msgstr` son iguales. **Si cambias un `string` de un campo o de una vista, debes actualizar también el `msgid` correspondiente en los `.po`**, o el texto viejo persistirá en la interfaz (la traducción guardada es la que se muestra).

## Procedimiento paso a paso

### Paso 1 — Cambia la cadena fuente en Python/XML

Siempre edita primero el `string` en el modelo o la vista. Ejemplo para renombrar "Cantidad" → "Ventas":

```python
# models/product_sale_report.py
qty_sold = fields.Float(string='Ventas', readonly=True)
```

### Paso 2 — Busca la cadena en las vistas XML

Si aparece en un título, `sum=` o menú, actualízala también (los textos de las vistas no usan las etiquetas de los campos):

```xml
<list string="IPV" default_group_by="product_id">
    <field name="gross_profit_amount" sum="Total ganancia"/>
</list>
```

### Paso 3 — Actualizar los archivos `.po`

Abrir `i18n/es.po` (y `es_419.po` si aplica), buscar el `msgid` viejo y cambiar **ambos** (msgid y msgstr):

```po
#: model_terms:ir.ui.view,arch_db:bi_analytics.view_bi_product_sale_report_list
msgid "Ventas"
msgstr "Ventas"
```

### Paso 4 — (Opcional) Regenerar el template `.pot`

Si querés regenerar el archivo maestro que Odoo mantiene (normalmente no es necesario para cambios de texto):

```bash
python3 odoo-bin -d <NOMBRE_DB> --i18n-export=/tmp/bi_analytics.pot --modules=bi_analytics --format=po --stop-after-init
```

### Paso 5 — Instalar/actualizar el módulo

Instalar/actualizar el módulo en Odoo para que se reescriba la interfaz:

```bash
python3 odoo-bin -d <NOMBRE_DB> -u bi_analytics --stop-after-init
```

O desde Odoo: *Configuración → Aplicaciones → Actualizar módulo*.

> Los cambios también requieren recargar la página del navegador (Ctrl+Shift+R).

## Ejemplo completo: renombrar un texto de reporte

Supon que querés cambiar "Importe de venta" → "Ventas netas":

1. `models/product_sale_report.py`:
   ```python
   sale_amount = fields.Monetary(string='Ventas netas', readonly=True)
   ```

2. `models/profitability_report.py`, `models/profitability_summary.py` — misma actualización en `sale_amount`.

3. En las vistas que usan el campo, si el título lo muestra por defecto no se edita nada; pero los `sum` (resúpimen de columna) se ajustan manualmente:
   ```xml
   <field name="sale_amount" sum="Total ventas netas"/>
   ```

4. `i18n/es.po` y `es_419.po`: cambiar `msgid "Importe de venta"` → `msgid "Ventas netas"`, con `msgstr "Ventas netas"`.

5. Actualizar el módulo con `-u bi_analytics`.