# Punto 3: productos del comerciante

Plan corto del ítem 3 de [`COMERCIOS.md`](COMERCIOS.md). Productos de `product.template` con comerciante; pantallas en el módulo; fuera del catálogo de Tienda Apk, del TPV y del menú de productos de Ventas. Sin subórdenes ni API.

## Alcance

- Campo `merchant_id` en `product.template` (`merchant_store.merchant`, `check_company=True`, `ondelete='restrict'`).
- Al guardar con comerciante: `company_id` = compañía del comerciante, `order_bridge_visible` = False, `available_in_pos` = False.
- Lista y formulario bajo **Comercios → Productos**: nombre, precio, imagen y activo; `merchant_id` obligatorio en esa vista.
- Catálogo Tienda Apk: `_order_bridge_product_domain` añade `merchant_id` vacío. `company_onboarding` compone con `super()`.
- Dominio `merchant_id` vacío en acciones de Productos (Ventas) y Productos (TPV).
- Versión `merchant_store` `19.0.1.2.0`. `company_onboarding` `19.0.1.4.3`. `order_bridge` no cambia de código.

## Fuera de este punto

Subórdenes, compra mixta, API, contrato de la app, reportes y acción de Ventas (puntos 4–8). Inventario no se toca.

## Comprobación

- Crear producto con comerciante; `company_id`, invisible en Tienda Apk y fuera del TPV.
- El dominio del catálogo lo excluye; un producto propio sin comerciante sigue dentro.
- Acciones de Productos (Ventas) y TPV llevan dominio que lo deja fuera.
- Un producto no acepta un comerciante de otra compañía.
- `./own_modules/scripts/run_tests.sh merchant_store`
- `./own_modules/scripts/run_tests.sh company_onboarding`
