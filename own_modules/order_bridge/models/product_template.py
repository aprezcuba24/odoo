# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    order_bridge_visible = fields.Boolean(
        string='Visible en Tienda Apk',
        help='Si está activo, las variantes de este producto pueden aparecer en el catálogo público de Tienda Apk y pedirse por la API (según empresa y reglas de venta).',
        default=False,
    )
