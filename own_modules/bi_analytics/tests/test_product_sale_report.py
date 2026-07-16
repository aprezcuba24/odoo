# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiProductSaleReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('point_of_sale.group_pos_manager')
        cls.partner = cls.env['res.partner'].create({'name': 'BI Test Customer'})
        cls.product = cls.env['product.product'].create({
            'name': 'BI Test Product',
            'sale_ok': True,
            'available_in_pos': True,
            'list_price': 10.0,
            'standard_price': 4.0,
        })
        cls.pos_product = cls.env['product.product'].create({
            'name': 'BI POS Test Product',
            'sale_ok': True,
            'available_in_pos': True,
            'list_price': 10.0,
            'standard_price': 4.0,
            'taxes_id': False,
        })
        cls.pos_payment_method = cls.env['pos.payment.method'].create({
            'name': 'BI Product Sale Bank',
            'receivable_account_id': cls.env.company.account_default_pos_receivable_account_id.id,
            'journal_id': cls.env['account.journal'].create({
                'name': 'BI Product Sale Bank',
                'code': 'BIPB',
                'type': 'bank',
                'company_id': cls.env.company.id,
            }).id,
        })
        cls.pos_config = cls.env['pos.config'].create({
            'name': 'BI Product Sale POS',
            'payment_method_ids': [Command.set(cls.pos_payment_method.ids)],
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

    def _create_paid_pos_order(self, qty, price_unit, total_cost, date_order=None):
        if not self.pos_config.current_session_id:
            self.pos_config.open_ui()

        price_subtotal = price_unit * qty
        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.pos_config.current_session_id.id,
            'amount_total': price_subtotal,
            'amount_tax': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'lines': [Command.create({
                'product_id': self.pos_product.id,
                'qty': qty,
                'price_unit': price_unit,
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal,
                'total_cost': total_cost,
                'is_total_cost_computed': True,
            })],
        })
        payment_context = {'active_ids': order.ids, 'active_id': order.id}
        payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'payment_method_id': self.pos_payment_method.id,
            'amount': price_subtotal,
        })
        payment.with_context(**payment_context).check()
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

    def test_product_sale_report_includes_paid_pos_order(self):
        order = self._create_paid_pos_order(2.0, 10.0, total_cost=8.0)
        self.assertIn(order.state, ('paid', 'done'))

        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.pos_product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.qty_sold, 2.0)
        self.assertAlmostEqual(report.sale_amount, 20.0)
        self.assertAlmostEqual(report.cost_amount, 8.0)
        self.assertAlmostEqual(report.profit_amount, 12.0)

    def test_product_sale_report_excludes_draft_pos_order(self):
        if not self.pos_config.current_session_id:
            self.pos_config.open_ui()

        self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.pos_config.current_session_id.id,
            'amount_total': 50.0,
            'amount_tax': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'lines': [Command.create({
                'product_id': self.pos_product.id,
                'qty': 5.0,
                'price_unit': 10.0,
                'price_subtotal': 50.0,
                'price_subtotal_incl': 50.0,
                'total_cost': 20.0,
                'is_total_cost_computed': True,
            })],
        })
        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.pos_product.id),
        ])
        self.assertFalse(report)
