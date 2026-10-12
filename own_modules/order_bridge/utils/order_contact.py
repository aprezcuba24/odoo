# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Datos de contacto del pedido Tienda Apk (teléfono y dirección de entrega)."""

from __future__ import annotations


def order_phone(order) -> str:
    """Teléfono del partner; si falta, el del dispositivo API."""
    phone = (order.partner_id.phone or '').strip()
    if not phone and order.order_bridge_device_id:
        phone = (order.order_bridge_device_id.phone or '').strip()
    return phone


def delivery_address_text(order) -> str:
    """Texto de la instantánea de dirección (calle, barrio, municipio, provincia)."""
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
    if snap.state and str(snap.state).strip():
        parts.append(str(snap.state).strip())
    return ', '.join(parts)
