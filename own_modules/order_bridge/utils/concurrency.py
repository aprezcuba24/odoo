# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Concurrency helpers for order_bridge API."""

# Namespace for product stock locks (two-key advisory lock; avoids clashing with device ids).
ORDER_BRIDGE_PRODUCT_STOCK_LOCK_NS = 0x4F425354  # 'OBST'


def pg_advisory_xact_lock_device(cr, device_id: int) -> None:
    """Serialize order creation per device until the HTTP transaction ends."""
    cr.execute('SELECT pg_advisory_xact_lock(%s)', (device_id,))


def pg_advisory_xact_lock_products(cr, product_ids) -> None:
    """Serialize stock reads/reserves for the given products until the transaction ends.

    Locks are taken in ascending id order to avoid deadlocks between POS checks and APK confirm.
    """
    for product_id in sorted({int(pid) for pid in product_ids if pid}):
        cr.execute(
            'SELECT pg_advisory_xact_lock(%s, %s)',
            (ORDER_BRIDGE_PRODUCT_STOCK_LOCK_NS, product_id),
        )
