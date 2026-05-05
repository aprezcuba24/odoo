# Order bridge API — ejemplos con curl

Sustituye `BASE` (p. ej. `http://localhost:8069`), `KEY` (UUID del dispositivo o clave generada por el cliente) y los IDs numéricos de ejemplo.

```bash
# Registro (sin Bearer): device_key obligatorio; phone y device_info opcionales
curl -sS -X POST "$BASE/api/order_bridge/register" \
  -H 'Content-Type: application/json' \
  -d '{"device_key":"'"$KEY"'","phone":"+34600111222","device_info":"Mi app v1"}'

# Estado del dispositivo / partner
curl -sS "$BASE/api/order_bridge/status" -H "Authorization: Bearer $KEY"

# Perfil (GET)
curl -sS "$BASE/api/order_bridge/profile" -H "Authorization: Bearer $KEY"

# Perfil completo (PUT: name + address con los cuatro campos)
curl -sS -X PUT "$BASE/api/order_bridge/profile" \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"Cliente Demo",
    "address":{
      "street":"Calle 1",
      "neighborhood":"Centro",
      "municipality":"Madrid",
      "state":"Madrid"
    }
  }'

# Perfil parcial (PATCH)
curl -sS -X PATCH "$BASE/api/order_bridge/profile" \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Nuevo nombre","address":{"street":"Calle 2"}}'

# Categorías POS (mismo conjunto que el TPV enlazado a la compañía)
curl -sS "$BASE/api/order_bridge/categories" -H "Authorization: Bearer $KEY"

# Catálogo paginado (productos del TPV)
# Query: limit (def. 80, máx. 200), offset, category_id, pos_category_id
curl -sS "$BASE/api/order_bridge/products?limit=10&offset=0" -H "Authorization: Bearer $KEY"
curl -sS "$BASE/api/order_bridge/products?pos_category_id=1" -H "Authorization: Bearer $KEY"

# Detalle de un producto
curl -sS "$BASE/api/order_bridge/products/123" -H "Authorization: Bearer $KEY"

# Listar pedidos (paginado: limit def. 50 máx. 200, offset, state opcional)
curl -sS "$BASE/api/order_bridge/orders?limit=20&offset=0" -H "Authorization: Bearer $KEY"
curl -sS "$BASE/api/order_bridge/orders?state=draft" -H "Authorization: Bearer $KEY"

# Crear pedido (qty > 0; alternativa: product_uom_qty en cada línea)
curl -sS -X POST "$BASE/api/order_bridge/orders" \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"lines":[{"product_id":123,"qty":1}]}'

# Detalle de un pedido (incluye líneas)
curl -sS "$BASE/api/order_bridge/orders/456" -H "Authorization: Bearer $KEY"

# Cancelar pedido (solo en borrador)
curl -sS -X POST "$BASE/api/order_bridge/orders/456/cancel" -H "Authorization: Bearer $KEY"
```

Preflight CORS: `curl -sS -X OPTIONS "$BASE/api/order_bridge/products" -i`.
