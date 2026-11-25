# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools.sql import SQL


class BiProfitabilityReport(models.Model):
    _inherit = 'bi.profitability.report'

    def _sale_order_sql_extra(self) -> SQL:
        return SQL('s.merchant_id IS NULL')
