# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Datos de contacto del pedido Tienda Apk (teléfono y dirección de entrega)."""

from __future__ import annotations


def order_phone(order) -> str:
    """Teléfono de la instantánea del pedido.

    Sin instantánea: teléfono del partner; si falta, el del dispositivo API.
    """
    snap = order.order_bridge_snapshot_address_id
    if snap:
        return (snap.phone or '').strip()
    phone = (order.partner_id.phone or '').strip()
    if not phone and order.order_bridge_device_id:
        phone = (order.order_bridge_device_id.phone or '').strip()
    return phone


def address_text(addr) -> str:
    """Texto (calle, barrio, municipio, provincia) de la instantánea o de la dirección del cliente."""
    if not addr:
        return ''
    parts = []
    if addr.street:
        parts.append(addr.street.strip())
    neighborhood = addr.neighborhood_id.name if addr.neighborhood_id else ''
    municipality = addr.municipality_id.name if addr.municipality_id else ''
    if neighborhood and municipality:
        parts.append(f'{neighborhood}. {municipality}')
    elif neighborhood:
        parts.append(neighborhood)
    elif municipality:
        parts.append(municipality)
    if addr.state and str(addr.state).strip():
        parts.append(str(addr.state).strip())
    return ', '.join(parts)


def delivery_address_text(order) -> str:
    """Texto de la instantánea de dirección (calle, barrio, municipio, provincia)."""
    return address_text(order.order_bridge_snapshot_address_id)
