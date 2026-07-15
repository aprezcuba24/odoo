# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiProfitabilityReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profitability_company = cls.env['res.company'].create({
            'name': 'BI Profitability Test Co',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'BI Profitability Customer',
            'company_id': cls.profitability_company.id,
        })
        cls.product = cls.env['product.product'].with_company(cls.profitability_company).create({
            'name': 'BI Profitability Product',
            'sale_ok': True,
            'list_price': 10.0,
            'standard_price': 4.0,
        })

    def _create_confirmed_order(self, qty, price_unit, date_order=None):
        order = self.env['sale.order'].with_company(self.profitability_company).create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
            })],
        })
        order.action_confirm()
        if date_order:
            order.date_order = date_order
        return order

    def _search_report(self, domain):
        return self.env['bi.profitability.report'].search(
            domain + [('company_id', '=', self.profitability_company.id)],
        )

    def test_profitability_report_shows_daily_sales(self):
        now = fields.Datetime.now()
        sale_date = fields.Date.to_date(now)

        self._create_confirmed_order(2.0, 10.0, date_order=now)

        report = self._search_report([
            ('date', '=', sale_date),
        ])
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.sale_amount, 20.0)
        self.assertAlmostEqual(report.product_cost_amount, 8.0)
        self.assertAlmostEqual(report.gross_profit_amount, 12.0)

    def test_profitability_report_filters_by_date(self):
        now = fields.Datetime.now()
        previous_month = now - relativedelta(months=1)
        current_sale_date = fields.Date.to_date(now)
        previous_sale_date = fields.Date.to_date(previous_month)

        self._create_confirmed_order(2.0, 10.0, date_order=now)
        self._create_confirmed_order(5.0, 10.0, date_order=previous_month)

        current_report = self._search_report([
            ('date', '=', current_sale_date),
        ])
        self.assertEqual(len(current_report), 1)
        self.assertAlmostEqual(current_report.sale_amount, 20.0)

        all_reports = self._search_report([
            ('date', 'in', [current_sale_date, previous_sale_date]),
        ])
        total_sales = sum(all_reports.mapped('sale_amount'))
        self.assertAlmostEqual(total_sales, 70.0)

    def test_profitability_report_shows_all_days_in_month(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        month_end = today.replace(day=days_in_month)
        sale_day = today.replace(day=min(15, days_in_month))
        # Noon UTC avoids date shifts when PostgreSQL casts timestamp to date.
        sale_datetime = fields.Datetime.to_datetime(sale_day).replace(hour=12)

        self._create_confirmed_order(2.0, 10.0, date_order=sale_datetime)

        report = self._search_report([
            ('date', '>=', month_start),
            ('date', '<=', month_end),
        ])
        self.assertEqual(len(report), days_in_month)

        sale_rows = report.filtered(lambda r: r.sale_amount)
        self.assertEqual(len(sale_rows), 1)
        self.assertAlmostEqual(sale_rows.sale_amount, 20.0)
        self.assertAlmostEqual(sale_rows.product_cost_amount, 8.0)
        self.assertAlmostEqual(sale_rows.gross_profit_amount, 12.0)

        empty_rows = report - sale_rows
        self.assertEqual(len(empty_rows), days_in_month - 1)
        self.assertTrue(all(amount == 0.0 for amount in empty_rows.mapped('sale_amount')))
        self.assertTrue(all(amount == 0.0 for amount in empty_rows.mapped('product_cost_amount')))
        self.assertTrue(all(amount == 0.0 for amount in empty_rows.mapped('gross_profit_amount')))
