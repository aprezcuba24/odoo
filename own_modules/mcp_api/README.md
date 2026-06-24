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
| Buscar clientes / productos | Ventas / Usuario (+ lectura contactos/productos) |
| Crear pedidos vía MCP (`api_create_confirmed_order`) | Ventas / Usuario + `order_bridge` instalado |

## Métodos expuestos

| Modelo | Método | Descripción |
|--------|--------|-------------|
| `sale.order` | `api_create_confirmed_order` | Pedido Tienda Apk (`order_bridge_origin=admin`): confirmación y reserva vía hooks de `order_bridge` |

Operaciones de solo lectura (clientes, productos, pedidos existentes) usan métodos ORM estándar (`search_read`, `read`, …) sin código en este módulo.

## Ejemplo JSON-2

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
