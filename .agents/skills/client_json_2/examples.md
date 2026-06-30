# JSON-2 client — examples

All examples assume `odoo = OdooClient.from_env()` from [SKILL.md](SKILL.md).

## Search Tienda Apk customers (with address)

Uses `api_search_customers` on `res.partner`. Optional `query` filters by name, phone or delivery address; omit to list APK customers.

```python
@mcp.tool
def search_customers(query: str | None = None, limit: int = 10) -> list[dict]:
    """Tienda Apk customers. Without query: list up to limit. With query: filter by name/phone/address."""
    params = {"limit": min(limit, 20)}
    if query is not None and str(query).strip():
        params["query"] = str(query).strip()
    return odoo.call("res.partner", "api_search_customers", **params)
```

## Get one customer by exact name

```python
def get_partner_by_exact_name(name: str) -> dict | None:
    rows = odoo.call(
        "res.partner",
        "search_read",
        domain=[
            ["name", "=", name],
            ["customer_rank", ">", 0],
        ],
        fields=["name", "email", "phone", "vat"],
        limit=2,
    )
    if len(rows) != 1:
        return None
    return rows[0]
```

## Search products by internal reference

```python
def get_products_by_refs(refs: list[str]) -> dict[str, int]:
    products = odoo.call(
        "product.product",
        "search_read",
        domain=[["default_code", "in", refs]],
        fields=["id", "default_code"],
    )
    return {p["default_code"]: p["id"] for p in products}
```

## Create draft sale order

```python
def create_draft_order(partner_id: int, lines: list[dict], ref: str | None = None) -> int:
    order_line = [
        [0, 0, {"product_id": line["product_id"], "product_uom_qty": line["qty"]}]
        for line in lines
    ]
    vals = {"partner_id": partner_id, "order_line": order_line}
    if ref:
        vals["client_order_ref"] = ref
    return odoo.call("sale.order", "create", vals_list=[vals])
```

## Create and confirm (single transaction — preferred)

Creates a Tienda Apk admin order (`order_bridge_origin=admin`) via `api_create_confirmed_order` on `sale.order`.

### 1. Find the customer (`partner_id`)

Search Tienda Apk customers first; use the `id` from the result as `partner_id`:

```python
customers = odoo.call(
    "res.partner",
    "api_search_customers",
    query="María",
    limit=5,
)
# → list[dict]; pick exactly one row before creating the order
partner_id = customers[0]["id"]
```

Example response (200):

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

If the customer has no delivery address, `"address"` is `false`.

### 2. Pass `lines`

`lines` is a **plain list of dicts** (not Odoo `(0, 0, vals)` tuples). Each line needs:

| Field | Required | Notes |
|-------|----------|-------|
| `product_id` | yes | `product.product` id |
| `qty` or `product_uom_qty` | yes | Positive quantity (either key works) |

```python
lines = [
    {"product_id": 7, "qty": 2},
    {"product_id": 12, "product_uom_qty": 1.5},
]
```

Resolve `product_id` beforehand (e.g. `search_read` on `default_code`) — the API does not accept SKU strings in `lines`.

### 3. Create and confirm

```python
def create_confirmed_order(partner_id: int, lines: list[dict], ref: str | None = None) -> dict:
    return odoo.call(
        "sale.order",
        "api_create_confirmed_order",
        partner_id=partner_id,
        lines=lines,
        client_order_ref=ref,
    )

# Full flow
customers = odoo.call("res.partner", "api_search_customers", query="María", limit=5)
order = create_confirmed_order(
    partner_id=customers[0]["id"],
    lines=[{"product_id": 7, "qty": 2}, {"product_id": 12, "qty": 1}],
    ref="PO-123",
)
```

Example response (200):

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

The order is created and confirmed in one transaction (`state` is already `"sale"`).

## Read sale order status

```python
def get_order(order_id: int) -> dict:
    rows = odoo.call(
        "sale.order",
        "read",
        ids=[order_id],
        fields=["name", "state", "amount_total", "partner_id", "invoice_status"],
    )
    return rows[0]
```

## MCP tool with ambiguity handling

```python
@mcp.tool
def find_customer(name: str) -> dict:
    """Find a single customer by name. Fails if zero or multiple matches."""
    partners = odoo.call(
        "res.partner",
        "search_read",
        domain=[["name", "ilike", name], ["customer_rank", ">", 0]],
        fields=["id", "name", "email"],
        limit=10,
    )
    if not partners:
        return {"error": "not_found", "query": name}
    if len(partners) > 1:
        return {
            "error": "ambiguous",
            "query": name,
            "candidates": partners,
        }
    return {"partner": partners[0]}
```

## Health check (no auth)

```python
import requests

def odoo_version(base_url: str) -> dict:
    r = requests.get(f"{base_url.rstrip('/')}/web/version", timeout=10)
    r.raise_for_status()
    return r.json()
```
