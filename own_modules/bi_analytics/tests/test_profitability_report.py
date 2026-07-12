# Part of Odoo. See LICENSE file for full copyright and licensing details.

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
        cls.fixed_category = cls.env.ref('bi_analytics.cost_category_fixed')

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

    def test_profitability_report_combines_sales_and_other_costs(self):
        now = fields.Datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        self._create_confirmed_order(2.0, 10.0, date_order=now)

        cost = self.env['bi.other.cost'].create({
            'name': 'Alquiler test',
            'date': fields.Date.to_date(now),
            'amount': 120.0,
            'category_id': self.fixed_category.id,
            'company_id': self.profitability_company.id,
            'currency_id': self.profitability_company.currency_id.id,
        })
        cost.action_confirm()

        report = self._search_report([
            ('date', '=', fields.Date.to_date(month_start)),
        ])
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.sale_amount, 20.0)
        self.assertAlmostEqual(report.product_cost_amount, 8.0)
        self.assertAlmostEqual(report.gross_profit_amount, 12.0)
        self.assertAlmostEqual(report.other_cost_amount, 120.0)
        self.assertAlmostEqual(report.net_profit_amount, -108.0)

    def test_profitability_report_shows_costs_without_sales(self):
        month_start = fields.Date.today().replace(day=1)
        cost = self.env['bi.other.cost'].create({
            'name': 'Solo gasto',
            'date': month_start,
            'amount': 75.0,
            'category_id': self.fixed_category.id,
            'company_id': self.profitability_company.id,
            'currency_id': self.profitability_company.currency_id.id,
        })
        cost.action_confirm()

        report = self._search_report([
            ('date', '=', month_start),
        ])
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.sale_amount, 0.0)
        self.assertAlmostEqual(report.other_cost_amount, 75.0)
        self.assertAlmostEqual(report.net_profit_amount, -75.0)

    def test_profitability_report_filters_by_date(self):
        now = fields.Datetime.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_month = current_month_start - relativedelta(months=1)

        self._create_confirmed_order(2.0, 10.0, date_order=now)
        self._create_confirmed_order(5.0, 10.0, date_order=previous_month)

        current_report = self._search_report([
            ('date', '=', fields.Date.to_date(current_month_start)),
        ])
        self.assertEqual(len(current_report), 1)
        self.assertAlmostEqual(current_report.sale_amount, 20.0)

        previous_month_start = previous_month.replace(day=1)
        all_reports = self._search_report([
            ('date', 'in', [
                fields.Date.to_date(current_month_start),
                fields.Date.to_date(previous_month_start),
            ]),
        ])
        total_sales = sum(all_reports.mapped('sale_amount'))
        self.assertAlmostEqual(total_sales, 70.0)
