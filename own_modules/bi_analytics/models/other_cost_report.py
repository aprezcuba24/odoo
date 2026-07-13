# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools.sql import SQL


class BiOtherCostReport(models.Model):
    _name = 'bi.other.cost.report'
    _description = 'Reporte de gastos'
    _auto = False
    _rec_name = 'name'
    _order = 'amount desc'

    name = fields.Char(string='Descripción', readonly=True)
    category_id = fields.Many2one('bi.cost.category', string='Categoría', readonly=True)
    cost_type = fields.Selection(
        selection=[
            ('fixed', 'Costo fijo'),
            ('supply', 'Insumo'),
            ('other', 'Otro'),
        ],
        string='Tipo de costo',
        readonly=True,
    )
    product_id = fields.Many2one('product.product', string='Insumo', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    date = fields.Date(string='Fecha', readonly=True)
    amount = fields.Monetary(string='Importe', readonly=True)

    _depends = {
        'bi.other.cost': [
            'state',
            'name',
            'category_id',
            'product_id',
            'company_id',
            'currency_id',
            'date',
            'amount',
        ],
        'bi.cost.category': ['cost_type'],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL('%s %s %s', self._select(), self._from(), self._where())

    def _select(self) -> SQL:
        return SQL(
            """
                SELECT
                    oc.id AS id,
                    oc.name AS name,
                    oc.category_id AS category_id,
                    cc.cost_type AS cost_type,
                    oc.product_id AS product_id,
                    oc.company_id AS company_id,
                    oc.currency_id AS currency_id,
                    oc.date AS date,
                    oc.amount AS amount
            """,
        )

    def _from(self) -> SQL:
        return SQL(
            """
                FROM bi_other_cost oc
                JOIN bi_cost_category cc ON cc.id = oc.category_id
            """,
        )

    def _where(self) -> SQL:
        return SQL(
            """
                WHERE oc.state = 'confirmed'
            """,
        )
