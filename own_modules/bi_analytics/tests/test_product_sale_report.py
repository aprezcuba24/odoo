# Part of Odoo. See LICENSE file for full copyright and licensing details.

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

    def test_product_sale_report_aggregates_confirmed_order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'price_unit': 10.0,
            })],
        })
        order.action_confirm()
        line = order.order_line
        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.qty_sold, 2.0)
        self.assertAlmostEqual(report.sale_amount, 10.0 * 2.0)
        self.assertAlmostEqual(report.cost_amount, line.purchase_price * 2.0)

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
