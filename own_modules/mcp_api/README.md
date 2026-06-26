# MCP API (JSON-2)

Métodos ORM del addon `mcp_api` invocables desde el servicio MCP externo vía JSON-2.

## Instalación

```bash
python3 odoo-bin -d DBNAME -i mcp_api --stop-after-init --no-http
```

Requiere `order_bridge` (dependencia del manifest) y el módulo core `rpc` (JSON-2).

## Autenticación por usuario

Cada persona que use el MCP debe ser un **`res.users`** normal en Odoo con los grupos funcionales que correspondan (p. ej. Ventas / Usuario).

1. Iniciar sesión en Odoo.
2. **Preferencias → Seguridad de la cuenta → Claves API**.
3. Crear una clave con scope **`rpc`**.
4. El servicio MCP envía esa clave en cada petición:

   ```http
   Authorization: Bearer <api_key>
   Content-Type: application/json; charset=utf-8
   ```

Odoo resuelve la clave al `uid` del propietario (`ir_http._auth_method_bearer`). Todas las llamadas ejecutan como ese usuario: **ACL y record rules** aplican igual que en la interfaz web.

No hay usuario bot compartido: en producción multi-usuario, el cliente MCP debe instanciar `OdooClient` **por sesión** con la key de quien opera, no una `ODOO_API_KEY` global.

### Permisos típicos

| Operación | Grupos Odoo |
|-----------|-------------|
| Buscar clientes Tienda Apk (`api_search_customers`) | Ventas / Usuario (+ lectura contactos) |
| Buscar productos Tienda Apk (`api_search_products`) | Ventas / Usuario (+ lectura productos) |
| Obtener producto Tienda Apk (`api_get_product`) | Ventas / Usuario (+ lectura productos) |
| Crear pedidos vía MCP (`api_create_confirmed_order`) | Ventas / Usuario + `order_bridge` instalado |

## Métodos expuestos

| Modelo | Método | Descripción |
|--------|--------|-------------|
| `res.partner` | `api_search_customers` | Clientes Tienda Apk (`order_bridge_registered`); `query` opcional (nombre/teléfono/dirección); devuelve dirección anidada |
| `product.product` | `api_search_products` | Productos disponibles para la tienda (catálogo Tienda Apk + stock); `query`, `category_id`, `limit`, `offset`; devuelve página con `items` y `total` |
| `product.product` | `api_get_product` | Un producto por `product_id`; misma disponibilidad que búsqueda; devuelve categoría anidada |
| `sale.order` | `api_create_confirmed_order` | Pedido Tienda Apk (`order_bridge_origin=admin`): confirmación y reserva vía hooks de `order_bridge` |

Otras lecturas (pedidos existentes) pueden usar métodos ORM estándar (`search_read`, `read`, …).

## Ejemplo JSON-2 — buscar clientes Tienda Apk

Parámetros: `query` (opcional; si se omite o está vacío, lista clientes APK sin filtro de texto), `limit` (default 10, máx. 20).

Listar sin filtro:

```bash
curl -sS -X POST "$ODOO_URL/json/2/res.partner/api_search_customers" \
  -H "Authorization: Bearer $USER_API_KEY" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"limit": 20}'
```

Buscar por nombre, teléfono o dirección:

```bash
curl -sS -X POST "$ODOO_URL/json/2/res.partner/api_search_customers" \
  -H "Authorization: Bearer $USER_API_KEY" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"query": "Centro", "limit": 10}'
```

Respuesta (200):

```json
[
  {
    "id": 42,
    "name": "María",
    "phone": "+34600000000",
    "order_bridge_registered": true,
    "order_bridge_phone_validated": false,
    "address": {
      "street": "Calle 10",
      "municipality_id": 3,
      "municipality_name": "Camagüey",
      "neighborhood_id": 15,
      "neighborhood_name": "Centro",
      "state": "Camagüey"
    }
  }
]
```

## Ejemplo JSON-2 — buscar productos Tienda Apk

Parámetros: `query` (opcional; nombre o categoría), `category_id` (opcional; `child_of`), `limit` (default 80, máx. 200), `offset` (default 0).

Solo devuelve productos **disponibles para la tienda**: catálogo Tienda Apk (`order_bridge_visible`, `sale_ok`, `active`) con stock (misma regla que `GET /api/order_bridge/products`). Los almacenables sin stock no aparecen; los servicios sí. `total` es el recuento tras el filtro de stock (antes de paginar).

Listar sin filtro:

```bash
curl -sS -X POST "$ODOO_URL/json/2/product.product/api_search_products" \
  -H "Authorization: Bearer $USER_API_KEY" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"limit": 20, "offset": 0}'
```

Buscar por nombre o categoría, o filtrar por categoría:

```bash
curl -sS -X POST "$ODOO_URL/json/2/product.product/api_search_products" \
  -H "Authorization: Bearer $USER_API_KEY" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"query": "Bebidas", "category_id": 3, "limit": 10, "offset": 0}'
```

Respuesta (200):

```json
{
  "items": [
    {
      "id": 7,
      "name": "Agua mineral",
      "default_code": false,
      "list_price": 0.8,
      "uom_name": "Units",
      "barcode": false,
      "category": {
        "id": 3,
        "name": "Bebidas",
        "parent_id": 1
      }
    }
  ],
  "limit": 10,
  "offset": 0,
  "total": 1
}
```

## Ejemplo JSON-2 — obtener producto Tienda Apk por id

Parámetro: `product_id` (entero). Misma disponibilidad que `api_search_products` (catálogo + stock). Si el producto no existe, no está en la tienda o no tiene stock, responde 422.

```bash
curl -sS -X POST "$ODOO_URL/json/2/product.product/api_get_product" \
  -H "Authorization: Bearer $USER_API_KEY" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"product_id": 7}'
```

Respuesta (200):

```json
{
  "id": 7,
  "name": "Agua mineral",
  "default_code": false,
  "list_price": 0.8,
  "uom_name": "Units",
  "barcode": false,
  "category": {
    "id": 3,
    "name": "Bebidas",
    "parent_id": 1
  }
}
```

## Ejemplo JSON-2 — crear pedido

```bash
curl -sS -X POST "$ODOO_URL/json/2/sale.order/api_create_confirmed_order" \
  -H "Authorization: Bearer $USER_API_KEY" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{
    "partner_id": 42,
    "lines": [{"product_id": 7, "qty": 2}],
    "client_order_ref": "PO-123"
  }'
```

Respuesta (200):

```json
{
  "id": 15,
  "name": "S00015",
  "state": "sale",
  "amount_total": 20.0,
  "partner_id": 42,
  "client_order_ref": "PO-123"
}
```

## Relación con `order_bridge`

| Canal | Ruta | Auth |
|-------|------|------|
| App móvil | `/api/order_bridge/*` | Bearer `device_key` |
| MCP | `/json/2/*` | Bearer API key de `res.users` |

La lógica compartida (reserva greedy, confirmación Tienda Apk) vive en `order_bridge`; `mcp_api` la reutiliza en `api_create_confirmed_order` vía `self.create()` sin duplicar controladores REST.

## Tests

```bash
python3 odoo-bin -d odoo \
  --addons-path=odoo/addons,addons,own_modules,oca \
  --test-tags /mcp_api \
  --stop-after-init --no-http --http-port=8071
```
