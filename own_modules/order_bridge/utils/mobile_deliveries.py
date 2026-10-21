# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Serialización y helpers para la API móvil de entregas (/api/mobile/v1)."""

from __future__ import annotations

from datetime import datetime, timezone

from odoo import fields
from odoo.tools.misc import format_amount

from odoo.addons.order_bridge.utils.order_contact import (
    delivery_address_text,
    order_phone,
)


def utc_now_iso_ms() -> str:
    """ISO-8601 UTC with milliseconds and Z suffix."""
    return datetime_to_iso_ms(datetime.now(timezone.utc))


def datetime_to_iso_ms(dt) -> str:
    """Format a datetime as ISO-8601 UTC with milliseconds and Z suffix."""
    if dt is None:
        return utc_now_iso_ms()
    if getattr(dt, 'tzinfo', None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{int(dt.microsecond / 1000):03d}Z'


def delivery_note_to_remote(note) -> dict:
    """Map order_bridge.delivery.note to the RemoteDelivery note shape."""
    return {
        'author': note.author,
        'body': note.body or '',
        'createdAt': datetime_to_iso_ms(note.create_date),
    }


def parse_device_timestamp(value) -> str | None:
    """Return normalized ISO string if ``value`` is a valid ISO-8601 datetime, else None."""
    if value is None or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    return raw


def delivery_point_from_partner(partner) -> dict | None:
    """WGS84 point from Tienda Apk address, or None if unset / incomplete."""
    if not partner:
        return None
    addr = partner.order_bridge_partner_address_ids[:1]
    if not addr:
        return None
    lat = float(addr.latitude or 0.0)
    lon = float(addr.longitude or 0.0)
    if lat == 0.0 or lon == 0.0:
        return None
    return {'longitude': lon, 'latitude': lat}


def order_delivery_date(order) -> str:
    """Order day as YYYY-MM-DD in the company timezone."""
    dt = order.date_order
    if not dt:
        return fields.Date.context_today(order).isoformat()
    tz = order.company_id.partner_id.tz or 'UTC'
    local = fields.Datetime.context_timestamp(order.with_context(tz=tz), dt)
    return local.date().isoformat()


def order_delivery_description(order) -> str:
    """GFM markdown table of product lines and total."""
    lines = order.order_bridge_report_product_lines()
    if not lines:
        return ''
    currency = order.currency_id
    rows = ['| Producto | Precio |', '| --- | ---: |']
    for line in lines:
        name = line.product_id.with_context(display_default_code=False).display_name or ''
        name = str(name).replace('|', '\\|')
        qty = line.product_uom_qty
        if qty and qty != 1.0:
            name = f'{name} × {qty:g}'
        amount = format_amount(order.env, line.price_subtotal, currency)
        rows.append(f'| {name} | {amount} |')
    total = format_amount(order.env, order.amount_total, currency)
    rows.append('')
    rows.append(f'**Total:** {total}')
    return '\n'.join(rows)


def order_to_remote_delivery(order) -> dict:
    """Map a sale.order to the RemoteDelivery JSON shape (camelCase)."""
    partner = order.partner_id
    notes = order.order_bridge_delivery_note_ids.sorted(
        key=lambda n: (n.create_date or fields.Datetime.now(), n.id),
    )
    return {
        'identifier': str(order.id),
        'reference': order.name or '',
        'customerName': partner.name or '',
        'customerPhone': order_phone(order) or '',
        'address': delivery_address_text(order) or '',
        'date': order_delivery_date(order),
        'description': order_delivery_description(order),
        'point': delivery_point_from_partner(partner),
        'notes': [delivery_note_to_remote(note) for note in notes],
    }
