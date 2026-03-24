# Mobile API — ejemplos con curl

Sustituye `BASE` (p. ej. `http://localhost:8069`) y `KEY` (UUID del dispositivo).

```bash
# Registro (sin Bearer)
curl -sS -X POST "$BASE/api/mobile/register" \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+34600111222","device_key":"'"$KEY"'","name":"Cliente Demo"}'

# Estado
curl -sS "$BASE/api/mobile/status" -H "Authorization: Bearer $KEY"

# Catálogo
curl -sS "$BASE/api/mobile/products?limit=10" -H "Authorization: Bearer $KEY"

# Crear pedido
curl -sS -X POST "$BASE/api/mobile/orders" \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"lines":[{"product_id":ID_PRODUCTO,"qty":1}]}'

# Listar pedidos
curl -sS "$BASE/api/mobile/orders" -H "Authorization: Bearer $KEY"
```

Preflight CORS: `curl -sS -X OPTIONS "$BASE/api/mobile/products" -i`.
