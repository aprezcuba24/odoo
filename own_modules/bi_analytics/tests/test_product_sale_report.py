# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiProductSaleReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'BI Test Customer'})
        cls.product = cls.env['product.product'].create({
            'name': 'BI Test Product',
            'sale_ok': True,
            'list_price': 10.0,
            'standard_price': 4.0,
        })

    def _create_confirmed_order(self, qty, price_unit, date_order=None):
        order = self.env['sale.order'].create({
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

    def test_product_sale_report_aggregates_confirmed_order(self):
        order = self._create_confirmed_order(2.0, 10.0)
        line = order.order_line
        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.qty_sold, 2.0)
        self.assertAlmostEqual(report.sale_amount, 10.0 * 2.0)
        self.assertAlmostEqual(report.cost_amount, line.purchase_price * 2.0)
        self.assertAlmostEqual(report.profit_amount, report.sale_amount - report.cost_amount)

    def test_product_sale_report_excludes_draft_orders(self):
        self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5.0,
                'price_unit': 10.0,
            })],
        })
        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.product.id),
        ])
        self.assertFalse(report)

    def test_product_sale_report_filters_by_date(self):
        now = fields.Datetime.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_month = current_month_start - relativedelta(months=1)

        self._create_confirmed_order(2.0, 10.0, date_order=now)
        self._create_confirmed_order(5.0, 10.0, date_order=previous_month)

        report_data = self.env['bi.product.sale.report'].read_group(
            domain=[
                ('product_id', '=', self.product.id),
                ('date_order', '>=', current_month_start),
                ('date_order', '<', current_month_start + relativedelta(months=1)),
            ],
            fields=['qty_sold', 'sale_amount'],
            groupby=['product_id'],
        )
        self.assertEqual(len(report_data), 1)
        self.assertEqual(report_data[0]['qty_sold'], 2.0)
        self.assertAlmostEqual(report_data[0]['sale_amount'], 20.0)

        all_data = self.env['bi.product.sale.report'].read_group(
            domain=[('product_id', '=', self.product.id)],
            fields=['qty_sold', 'sale_amount'],
            groupby=['product_id'],
        )
        self.assertEqual(all_data[0]['qty_sold'], 7.0)
        self.assertAlmostEqual(all_data[0]['sale_amount'], 70.0)
