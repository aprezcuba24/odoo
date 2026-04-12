# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Stock availability checks for order_bridge API (used from Pydantic validation)."""

from __future__ import annotations

from collections import defaultdict

from odoo.tools.float_utils import float_compare


class InsufficientStockError(Exception):
    """Raised when storable products lack free quantity; ``products`` lists shortages."""

    def __init__(self, products: list[dict]):
        self.products = products
        super().__init__('Stock insuficiente')


def validate_order_lines_stock(env, catalog_company, product_domain, lines):
    """Raise ``ValueError`` if storable products lack free quantity for the default warehouse.

    ``lines`` is an iterable of objects with ``product_id`` and ``qty`` (e.g. ``OrderLineIn``).

    Skips stock check when ``sale_stock`` is not loaded (should not happen if manifest is correct).

    Uses superuser environment because API routes run as public user but must read warehouses
    and products.
    """
    env = env(su=True)
    if 'stock.warehouse' not in env:
        return
    warehouse = env['stock.warehouse'].search(
        [('company_id', '=', catalog_company.id)],
        limit=1,
    )
    if not warehouse:
        raise ValueError('No hay almacén configurado para la compañía del catálogo')

    qty_by_product = defaultdict(float)
    for line in lines:
        qty_by_product[line.product_id] += line.qty

    Product = env['product.product'].with_company(catalog_company)
    precision = env['decimal.precision'].precision_get('Product Unit')

    insufficient: list[dict] = []
    for product_id, need in qty_by_product.items():
        product = Product.browse(product_id).exists()
        if not product or not product.filtered_domain(product_domain):
            raise ValueError(f'el producto {product_id} no está disponible')
        if product.type == 'service' or not product.is_storable:
            continue
        product_wh = product.with_context(warehouse_id=warehouse.id)
        free = product_wh.free_qty
        if float_compare(free, need, precision_digits=precision) < 0:
            insufficient.append({
                'product_id': product.id,
                'available_qty': float(free),
            })
    if insufficient:
        raise InsufficientStockError(insufficient)
