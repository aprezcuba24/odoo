# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    def _where_sale(self):
        return super()._where_sale() + """
            AND s.merchant_id IS NULL"""
