# Part of Odoo. See LICENSE file for full copyright and licensing details.

import pytz

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
        'pos.order': ['state', 'company_id', 'date_order'],
        'pos.order.line': [
            'product_id',
            'qty',
            'price_subtotal',
            'total_cost',
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

    def _pos_linked_sale_filter(self) -> SQL:
        if 'sale_order_line_id' in self.env['pos.order.line']._fields:
            return SQL('AND l.sale_order_line_id IS NULL')
        return SQL('')

    def _report_timezone(self) -> str:
        """Timezone used to turn UTC datetimes into calendar dates."""
        tz = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        if tz not in pytz.all_timezones_set:
            return 'UTC'
        return tz

    def _local_date_sql(self, datetime_sql: SQL) -> SQL:
        """Cast a UTC timestamp to a date in the current user's timezone."""
        return SQL(
            "(timezone(%s, timezone('UTC', %s)))::date",
            self._report_timezone(),
            datetime_sql,
        )

    def _from(self) -> SQL:
        return SQL(
            """
                FROM res_company c
                CROSS JOIN LATERAL generate_series(
                    date_trunc(
                        'month',
                        (
                            SELECT COALESCE(
                                (
                                    SELECT MIN(first_date)
                                    FROM (
                                        SELECT MIN(%s) AS first_date
                                        FROM sale_order s
                                        WHERE s.state = 'sale'
                                          AND s.company_id = c.id
                                        UNION ALL
                                        SELECT MIN(%s) AS first_date
                                        FROM pos_order o
                                        WHERE o.state IN ('paid', 'done')
                                          AND o.company_id = c.id
                                    ) dates
                                ),
                                CURRENT_DATE
                            )
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
                        company_id,
                        period_date,
                        SUM(sale_amount) AS sale_amount,
                        SUM(product_cost_amount) AS product_cost_amount
                    FROM (
                        SELECT
                            s.company_id AS company_id,
                            %s AS period_date,
                            l.price_unit * l.product_uom_qty AS sale_amount,
                            l.purchase_price * l.product_uom_qty AS product_cost_amount
                        FROM sale_order_line l
                        JOIN sale_order s ON s.id = l.order_id
                        WHERE s.state = 'sale'
                          AND l.display_type IS NULL
                          AND l.product_id IS NOT NULL
                        UNION ALL
                        SELECT
                            o.company_id AS company_id,
                            %s AS period_date,
                            l.price_subtotal AS sale_amount,
                            COALESCE(l.total_cost, 0) AS product_cost_amount
                        FROM pos_order_line l
                        JOIN pos_order o ON o.id = l.order_id
                        WHERE o.state IN ('paid', 'done')
                          AND l.product_id IS NOT NULL
                          %s
                    ) combined
                    GROUP BY company_id, period_date
                ) sales ON (
                    sales.company_id = c.id
                    AND sales.period_date = cal.period_date
                )
            """,
            self._local_date_sql(SQL('s.date_order')),
            self._local_date_sql(SQL('o.date_order')),
            self._local_date_sql(SQL('s.date_order')),
            self._local_date_sql(SQL('o.date_order')),
            self._pos_linked_sale_filter(),
        )
