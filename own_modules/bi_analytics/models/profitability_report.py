# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools.sql import SQL


class BiProfitabilityReport(models.Model):
    _name = 'bi.profitability.report'
    _description = 'Resumen de rentabilidad'
    _auto = False
    _rec_name = 'date'
    _order = 'date desc'

    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    date = fields.Date(string='Período', readonly=True)
    sale_amount = fields.Monetary(string='Ventas', readonly=True)
    product_cost_amount = fields.Monetary(string='Costo de productos', readonly=True)
    gross_profit_amount = fields.Monetary(string='Margen bruto', readonly=True)
    other_cost_amount = fields.Monetary(string='Otros costos', readonly=True)
    net_profit_amount = fields.Monetary(string='Ganancia neta', readonly=True)

    _depends = {
        'sale.order': ['state', 'company_id', 'date_order'],
        'sale.order.line': [
            'product_id',
            'product_uom_qty',
            'price_unit',
            'purchase_price',
            'display_type',
        ],
        'bi.other.cost': ['state', 'company_id', 'currency_id', 'date', 'amount'],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL('%s %s', self._select(), self._from())

    def _select(self) -> SQL:
        return SQL(
            """
                SELECT
                    (
                        (COALESCE(sales.company_id, costs.company_id) * 100000)
                        + (EXTRACT(YEAR FROM COALESCE(sales.period_date, costs.period_date))::int * 100)
                        + EXTRACT(MONTH FROM COALESCE(sales.period_date, costs.period_date))::int
                    ) AS id,
                    COALESCE(sales.company_id, costs.company_id) AS company_id,
                    COALESCE(sales.currency_id, costs.currency_id) AS currency_id,
                    COALESCE(sales.period_date, costs.period_date) AS date,
                    COALESCE(sales.sale_amount, 0) AS sale_amount,
                    COALESCE(sales.product_cost_amount, 0) AS product_cost_amount,
                    COALESCE(sales.sale_amount, 0) - COALESCE(sales.product_cost_amount, 0) AS gross_profit_amount,
                    COALESCE(costs.other_cost_amount, 0) AS other_cost_amount,
                    (
                        COALESCE(sales.sale_amount, 0)
                        - COALESCE(sales.product_cost_amount, 0)
                        - COALESCE(costs.other_cost_amount, 0)
                    ) AS net_profit_amount
            """,
        )

    def _from(self) -> SQL:
        return SQL(
            """
                FROM (
                    SELECT
                        s.company_id AS company_id,
                        c.currency_id AS currency_id,
                        date_trunc('month', s.date_order)::date AS period_date,
                        SUM(l.price_unit * l.product_uom_qty) AS sale_amount,
                        SUM(l.purchase_price * l.product_uom_qty) AS product_cost_amount
                    FROM sale_order_line l
                    JOIN sale_order s ON s.id = l.order_id
                    JOIN res_company c ON c.id = s.company_id
                    WHERE s.state = 'sale'
                      AND l.display_type IS NULL
                      AND l.product_id IS NOT NULL
                    GROUP BY s.company_id, c.currency_id, date_trunc('month', s.date_order)
                ) sales
                FULL OUTER JOIN (
                    SELECT
                        oc.company_id AS company_id,
                        oc.currency_id AS currency_id,
                        date_trunc('month', oc.date)::date AS period_date,
                        SUM(oc.amount) AS other_cost_amount
                    FROM bi_other_cost oc
                    WHERE oc.state = 'confirmed'
                    GROUP BY oc.company_id, oc.currency_id, date_trunc('month', oc.date)
                ) costs ON (
                    sales.company_id = costs.company_id
                    AND sales.currency_id = costs.currency_id
                    AND sales.period_date = costs.period_date
                )
            """,
        )
