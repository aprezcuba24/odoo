---
name: client_json_2
description: >-
  Odoo 19 JSON-2 API client (OdooClient) used by the external MCP service.
  Use when implementing or extending MCP tools, calling Odoo from Python,
  searching partners/customers, products, sale orders, or when the user
  mentions JSON-2, /json/2, OdooClient, odoo_client, or Odoo external API.
---

# Odoo JSON-2 client (`client_json_2`)

## Before writing code

1. Read the live client in your external MCP package (`odoo_client.py`). If absent, use the canonical client below.
2. Match its API (`call`, headers, env vars, error type). Do not invent a second HTTP client.
3. New capabilities = **MCP tool** that delegates to `odoo.call(model, method, **params)` — not raw `requests` in each tool.

## Environment

| Variable | Required | Purpose |
|----------|----------|---------|
| `ODOO_URL` | Yes | Base URL, no trailing slash |
| `ODOO_API_KEY` | Per session | Bearer token of the authenticated `res.users` (scope `rpc`). Dev-only fallback via env. |
| `ODOO_DATABASE` | If multi-DB | Sent as `X-Odoo-Database` |
| `ODOO_LANG` | No | Default `es_ES` in `context` |
| `ODOO_TIMEOUT` | No | HTTP timeout seconds (default 60) |

Never use `/xmlrpc`, `/jsonrpc`, or user passwords.

## Canonical client

```python
import os
import requests


class OdooAPIError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Odoo {status}: {body}")
        self.status = status
        self.body = body


class OdooClient:
    def __init__(
        self,
        url: str,
        api_key: str,
        database: str | None = None,
        lang: str = "es_ES",
        timeout: float = 60,
    ):
        self.base = f"{url.rstrip('/')}/json/2"
        self.lang = lang
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "odoo-mcp/1.0",
        })
        if database:
            self.session.headers["X-Odoo-Database"] = database

    @classmethod
    def from_env(cls) -> "OdooClient":
        """Single-user dev helper. Production MCP must pass each user's API key to the constructor."""
        return cls(
            url=os.environ["ODOO_URL"],
            api_key=os.environ["ODOO_API_KEY"],
            database=os.environ.get("ODOO_DATABASE"),
            lang=os.environ.get("ODOO_LANG", "es_ES"),
            timeout=float(os.environ.get("ODOO_TIMEOUT", "60")),
        )

    def call(self, model: str, method: str, **params):
        if "context" not in params:
            params["context"] = {"lang": self.lang}
        r = self.session.post(
            f"{self.base}/{model}/{method}",
            json=params,
            timeout=self.timeout,
        )
        if not r.ok:
            raise OdooAPIError(r.status_code, r.text)
        return r.json()
```

### `call()` contract

- **URL:** `POST {ODOO_URL}/json/2/{model}/{method}`
- **Body:** named ORM kwargs only (`domain`, `fields`, `ids`, `vals_list`, `context`, …)
- **Success:** parsed JSON return value directly (no `jsonrpc` envelope)
- **`@api.model` methods** (`create`, `search`, `search_read`): do **not** pass `ids`
- **Record methods** (`read`, `write`, `action_confirm`): pass `ids: [int, …]`
- **`create` (Odoo 19):** use `vals_list=[{...}]`; returns a single `int` id when one record

## MCP tool pattern

```python
from fastmcp import FastMCP
from odoo_client import OdooClient

mcp = FastMCP("odoo")

@mcp.tool
def my_tool(arg: str, api_key: str) -> list[dict]:
    """One-line description for the LLM."""
    odoo = OdooClient(url=os.environ["ODOO_URL"], api_key=api_key, ...)
    return odoo.call("model.name", "method_name", ...)
```

Rules for tools:

- One business concern per tool; docstring explains filters and return shape.
- Prefer `search_read` over `search` + `read`.
- Composite workflows (create + confirm) → one Odoo method (e.g. `api_create_confirmed_order`), one `call()`.
- Validate ambiguous search results (0 / 1 / N) in the tool before returning.

## Reference: search customers by name

This is the template for read-only list tools.

```python
@mcp.tool
def search_partner_by_name(name: str, limit: int = 5) -> list[dict]:
    """Search customers by partial name match. Returns id, name, email, phone, vat."""
    partners = odoo.call(
        "res.partner",
        "search_read",
        domain=[
            ["name", "ilike", name],
            ["customer_rank", ">", 0],
        ],
        fields=["name", "email", "phone", "vat"],
        limit=min(limit, 20),
    )
    if not partners:
        return []
    return partners
```

To implement a **new search** (products, orders, …): same shape — pick model, `search_read`, sensible `domain`/`fields`/`limit`, return JSON-serializable dicts.

| Target | Model | Typical domain |
|--------|-------|----------------|
| Customer | `res.partner` | `[["name","ilike",q], ["customer_rank",">",0]]` |
| Product | `product.product` | `[["default_code","=",ref]]` or `[["name","ilike",q]]` |
| Sale order | `sale.order` | `[["name","ilike",ref]]` or `[["partner_id","=",id]]` |

## Write operations

- **Draft order:** `sale.order` / `create` with `vals_list` and `order_line` as `[0, 0, {product_id, product_uom_qty}]`.
- **Create + confirm (production):** single call to `sale.order` / `api_create_confirmed_order` (Tienda Apk admin order via `order_bridge` hooks).
- Do not chain `create` + `action_confirm` across separate tools in production (separate transactions).

## Authentication (per user)

Each MCP operator is a normal **`res.users`** with their own API key (scope `rpc`). Odoo maps the Bearer token to that user; ACL and record rules apply as in the web UI. Instantiate `OdooClient(url=..., api_key=user_key)` per session — do not share one global key in production. See [`own_modules/mcp_api/README.md`](../../own_modules/mcp_api/README.md).

## Custom Odoo methods (`mcp_api` addon)

| Model | Method | Purpose |
|-------|--------|---------|
| `res.partner` | `api_search_customers` | Tienda Apk customers (`order_bridge_registered`); optional `query` (name/phone/address); nested delivery address |
| `sale.order` | `api_create_confirmed_order` | Tienda Apk admin order (`order_bridge_origin=admin`; confirm + greedy reservation via `order_bridge.create`) |

Read-only operations use standard ORM methods (`search_read`, `read`, …) with the user's permissions.

## Errors

| HTTP | Meaning |
|------|---------|
| 401 | Missing/invalid API key |
| 403 | Authenticated user lacks ACL / record rules |
| 404 | Unknown model/method or private method |
| 422 | Bad args (e.g. `ids` on `create`) |

`OdooAPIError.body` is JSON with `name`, `message`, `debug`.

## Not JSON-2

- **`order_bridge`** (`/api/order_bridge/`, Bearer `device_key`): mobile app only — not the MCP Odoo client.
- **OpenAPI:** `GET /order_bridge/static/openapi.json`

## More examples

See [examples.md](examples.md) for products, orders, and helper patterns.
