# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Formato Markdown legacy para notificaciones Telegram de pedidos Tienda Apk."""

from __future__ import annotations

from odoo.addons.order_bridge.utils.telegram_client import (
    escape_markdown,
    format_money,
    format_qty,
)


def _delivery_address_text(order) -> str:
    snap = order.order_bridge_snapshot_address_id
    if not snap:
        return ''
    parts = []
    if snap.street:
        parts.append(snap.street.strip())
    neighborhood = snap.neighborhood_id.name if snap.neighborhood_id else ''
    municipality = snap.municipality_id.name if snap.municipality_id else ''
    if neighborhood and municipality:
        parts.append(f'{neighborhood}. {municipality}')
    elif neighborhood:
        parts.append(neighborhood)
    elif municipality:
        parts.append(municipality)
    return ', '.join(parts)


def _order_phone(order) -> str:
    phone = (order.partner_id.phone or '').strip()
    if not phone and order.order_bridge_device_id:
        phone = (order.order_bridge_device_id.phone or '').strip()
    return phone


def format_order_created_message(order) -> str:
    """Construye el texto del mensaje con etiquetas en negrita (*...*)."""
    ref = escape_markdown(order.order_bridge_ref or order.name or '')
    client = escape_markdown(order.partner_id.name or '')
    phone = escape_markdown(_order_phone(order))
    address = escape_markdown(_delivery_address_text(order))

    lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)
    product_lines = []
    for line in lines:
        name = escape_markdown(line.name)
        qty = format_qty(order, line.product_uom_qty)
        price_unit = format_money(order, line.price_unit)
        subtotal = format_money(order, line.price_subtotal)
        product_lines.append(f'👉 {name}: {qty} x {price_unit} = {subtotal}')

    products_block = '\n'.join(product_lines) if product_lines else escape_markdown('-')
    total = format_money(order, order.amount_total)

    return (
        '*🛒 Nueva orden*\n'
        '\n'
        f'*Orden de compra:* {ref}\n'
        f'*Cliente:* {client}\n'
        f'*Teléfono:* {phone}\n'
        f'*Dirección:* {address}\n'
        '\n'
        '*Productos*\n'
        f'{products_block}\n'
        '\n'
        f'*Total:* {total}'
    )
