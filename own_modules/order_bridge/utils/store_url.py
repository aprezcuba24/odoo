# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Public storefront URLs for Tienda Apk products (WhatsApp publisher / product form)."""

from __future__ import annotations

import os

_DEFAULT_STORE_WEB_BASE_DOMAIN = 'vendelo360.app'


def order_bridge_store_web_base_domain() -> str:
    """Hostname after the company slug (no scheme, no trailing slash).

    Override with ``ORDER_BRIDGE_STORE_WEB_BASE_DOMAIN`` (e.g. ``vendelo360.app``).
    """
    raw = (os.environ.get('ORDER_BRIDGE_STORE_WEB_BASE_DOMAIN') or '').strip()
    if not raw:
        return _DEFAULT_STORE_WEB_BASE_DOMAIN
    # Allow accidental scheme or trailing slash in env.
    raw = raw.removeprefix('https://').removeprefix('http://').rstrip('/')
    return raw or _DEFAULT_STORE_WEB_BASE_DOMAIN


def order_bridge_product_store_url(company, product_id) -> str | bool:
    """Absolute product URL for the public store web, or False if no company slug.

    Example: ``https://yymercado.vendelo360.app/303`` when
    ``company.order_bridge_slug == 'yymercado'`` and ``product_id == 303``.
    """
    if not product_id:
        return False
    slug = (getattr(company, 'order_bridge_slug', None) or '').strip().lower()
    if not slug:
        return False
    domain = order_bridge_store_web_base_domain()
    return f'https://{slug}.{domain}/{int(product_id)}'
