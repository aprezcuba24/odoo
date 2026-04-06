# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    order_bridge_visible = fields.Boolean(
        string='Visible in Order bridge',
        help='If enabled, this product’s variants can appear in the Order Bridge public catalog and be ordered via the API (subject to company and sale rules).',
        default=False,
    )
