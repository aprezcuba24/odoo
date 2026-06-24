# JSON-2 client — examples

All examples assume `odoo = OdooClient.from_env()` from [SKILL.md](SKILL.md).

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

Creates a Tienda Apk admin order (`order_bridge_origin=admin`) via `api_create_confirmed_order` on `sale.order`:

```python
def create_confirmed_order(partner_id: int, lines: list[dict], ref: str | None = None) -> dict:
    return odoo.call(
        "sale.order",
        "api_create_confirmed_order",
        partner_id=partner_id,
        lines=lines,
        client_order_ref=ref,
    )
```

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
