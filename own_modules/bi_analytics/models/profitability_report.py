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
    date = fields.Date(string='Fecha', readonly=True)
    sale_amount = fields.Monetary(string='Ventas', readonly=True)
    product_cost_amount = fields.Monetary(string='Costo de productos', readonly=True)
    gross_profit_amount = fields.Monetary(string='Margen bruto', readonly=True)

    _depends = {
        'sale.order': ['state', 'company_id', 'date_order'],
        'sale.order.line': [
            'product_id',
            'product_uom_qty',
            'price_unit',
            'purchase_price',
            'display_type',
        ],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL('%s %s', self._select(), self._from())

    def _select(self) -> SQL:
        return SQL(
            """
                SELECT
                    (
                        (c.id * 1000000)
                        + to_char(cal.period_date, 'YYYYMMDD')::int
                    ) AS id,
                    c.id AS company_id,
                    c.currency_id AS currency_id,
                    cal.period_date AS date,
                    COALESCE(sales.sale_amount, 0) AS sale_amount,
                    COALESCE(sales.product_cost_amount, 0) AS product_cost_amount,
                    COALESCE(sales.sale_amount, 0) - COALESCE(sales.product_cost_amount, 0) AS gross_profit_amount
            """,
        )

    def _from(self) -> SQL:
        return SQL(
            """
                FROM res_company c
                CROSS JOIN LATERAL generate_series(
                    date_trunc(
                        'month',
                        (
                            SELECT COALESCE(MIN(s.date_order::date), CURRENT_DATE)
                            FROM sale_order s
                            WHERE s.state = 'sale'
                              AND s.company_id = c.id
                        )
                    )::date,
                    (
                        date_trunc('month', CURRENT_DATE)
                        + INTERVAL '1 month'
                        - INTERVAL '1 day'
                    )::date,
                    INTERVAL '1 day'
                ) AS cal(period_date)
                LEFT JOIN (
                    SELECT
                        s.company_id AS company_id,
                        s.date_order::date AS period_date,
                        SUM(l.price_unit * l.product_uom_qty) AS sale_amount,
                        SUM(l.purchase_price * l.product_uom_qty) AS product_cost_amount
                    FROM sale_order_line l
                    JOIN sale_order s ON s.id = l.order_id
                    WHERE s.state = 'sale'
                      AND l.display_type IS NULL
                      AND l.product_id IS NOT NULL
                    GROUP BY s.company_id, s.date_order::date
                ) sales ON (
                    sales.company_id = c.id
                    AND sales.period_date = cal.period_date
                )
            """,
        )
