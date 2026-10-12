# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Formato Markdown legacy para notificaciones Telegram de pedidos Tienda Apk."""

from __future__ import annotations

from odoo.addons.order_bridge.utils.order_contact import delivery_address_text, order_phone
from odoo.addons.order_bridge.utils.serialization import _coupon_fields_from_order
from odoo.addons.order_bridge.utils.telegram_client import (
    escape_markdown,
    format_money,
    format_qty,
)


def format_order_created_message(order) -> str:
    """Construye el texto del mensaje con etiquetas en negrita (*...*)."""
    ref = escape_markdown(order.name or '')
    client = escape_markdown(order.partner_id.name or '')
    phone = escape_markdown(order_phone(order))
    address = escape_markdown(delivery_address_text(order))

    lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)
    product_lines = []
    for line in lines:
        product = line.product_id.with_context(display_default_code=False)
        name = escape_markdown(product.display_name)
        qty = format_qty(order, line.product_uom_qty)
        price_unit = format_money(order, line.price_unit)
        subtotal = format_money(order, line.price_subtotal)
        product_lines.append(f'👉 {name}: {qty} x {price_unit} = {subtotal}')

    products_block = '\n'.join(product_lines) if product_lines else escape_markdown('-')
    total = format_money(order, order.amount_total)

    promo_code, discount_amount = _coupon_fields_from_order(order)
    coupon_block = ''
    if promo_code:
        code = escape_markdown(promo_code)
        discount = format_money(order, discount_amount)
        coupon_block = (
            f'\n*Cupón de descuento:* {code}\n'
            f'*Descuento:* {discount}\n'
        )

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
        f'{coupon_block}'
        '\n'
        f'*Total:* {total}'
    )
