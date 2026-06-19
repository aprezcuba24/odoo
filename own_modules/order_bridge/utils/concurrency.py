# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Concurrency helpers for order_bridge API."""


def pg_advisory_xact_lock_device(cr, device_id: int) -> None:
    """Serialize order creation per device until the HTTP transaction ends."""
    cr.execute('SELECT pg_advisory_xact_lock(%s)', (device_id,))
