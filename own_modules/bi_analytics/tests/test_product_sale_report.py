# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_is_zero


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
        cls.storable_product = cls.env['product.product'].create({
            'name': 'BI Storable Test Product',
            'sale_ok': True,
            'is_storable': True,
            'list_price': 10.0,
            'standard_price': 4.0,
        })
        wh = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        cls.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': cls.storable_product.id,
            'location_id': wh.lot_stock_id.id,
            'inventory_quantity': 50.0,
        }).action_apply_inventory()
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

    def _create_confirmed_order(self, qty, price_unit, date_order=None, product=None):
        product = product or self.product
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
            })],
        })
        order.action_confirm()
        if date_order:
            order.date_order = date_order
        return order

    def _validate_outgoing_picking(self, order):
        picking = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing' and p.state != 'done',
        )[:1]
        self.assertTrue(picking)
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()
        return picking

    def _return_picking(self, picking, qty):
        return_wiz = self.env['stock.return.picking'].with_context(
            active_id=picking.id,
            active_model='stock.picking',
        ).create({})
        for ret_line in return_wiz.product_return_moves:
            ret_line.quantity = qty
        res = return_wiz.action_create_returns()
        return_picking = self.env['stock.picking'].browse(res['res_id'])
        return_picking.action_confirm()
        return_picking.action_assign()
        for move in return_picking.move_ids:
            mlines = move.move_line_ids
            if mlines:
                mlines.quantity = move.product_uom_qty
            move.picked = True
        return_picking.button_validate()
        return return_picking

    def _create_paid_pos_order(self, qty, price_unit, total_cost, date_order=None, price_subtotal=None):
        if not self.pos_config.current_session_id:
            self.pos_config.open_ui()

        # POS refund lines keep a positive subtotal with negative qty.
        if price_subtotal is None:
            price_subtotal = abs(price_unit * qty) if qty < 0 else price_unit * qty
        payment_amount = -price_subtotal if qty < 0 else price_subtotal
        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.pos_config.current_session_id.id,
            'amount_total': payment_amount,
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
            'amount': payment_amount,
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

    def test_product_sale_report_signs_pos_refund_line(self):
        """POS refunds store negative qty and positive price_subtotal."""
        order = self._create_paid_pos_order(
            -1.0, 10.0, total_cost=-4.0, price_subtotal=10.0,
        )
        self.assertIn(order.state, ('paid', 'done'))
        self.assertEqual(order.lines.qty, -1.0)
        self.assertAlmostEqual(order.lines.price_subtotal, 10.0)
        self.assertAlmostEqual(order.lines.total_cost, -4.0)

        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.pos_product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.qty_sold, -1.0)
        self.assertAlmostEqual(report.sale_amount, -10.0)
        self.assertAlmostEqual(report.cost_amount, -4.0)
        self.assertAlmostEqual(report.profit_amount, -6.0)

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

    def test_product_sale_report_undelivered_order_unchanged(self):
        """Confirmed but not yet delivered orders still use ordered qty."""
        order = self._create_confirmed_order(2.0, 10.0, product=self.storable_product)
        line = order.order_line
        self.assertTrue(float_is_zero(line.qty_delivered, precision_rounding=line.product_uom_id.rounding))

        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.storable_product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.qty_sold, 2.0)
        self.assertAlmostEqual(report.sale_amount, 20.0)

    def test_product_sale_report_excludes_full_delivery_return(self):
        """Fully returned deliveries must not appear as sales."""
        order = self._create_confirmed_order(2.0, 10.0, product=self.storable_product)
        picking = self._validate_outgoing_picking(order)
        line = order.order_line
        self.assertAlmostEqual(line.qty_delivered, 2.0)

        report_before = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.storable_product.id),
        ])
        self.assertEqual(len(report_before), 1)
        self.assertEqual(report_before.qty_sold, 2.0)

        self._return_picking(picking, 2.0)
        self.assertTrue(
            float_is_zero(line.qty_delivered, precision_rounding=line.product_uom_id.rounding),
        )

        report_after = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.storable_product.id),
        ])
        self.assertFalse(report_after)

    def test_product_sale_report_partial_return_uses_net_qty(self):
        """Partial returns report the remaining delivered quantity."""
        order = self._create_confirmed_order(5.0, 10.0, product=self.storable_product)
        picking = self._validate_outgoing_picking(order)
        line = order.order_line
        self.assertAlmostEqual(line.qty_delivered, 5.0)

        self._return_picking(picking, 2.0)
        self.assertAlmostEqual(line.qty_delivered, 3.0)

        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.storable_product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.qty_sold, 3.0)
        self.assertAlmostEqual(report.sale_amount, 30.0)
        self.assertAlmostEqual(report.cost_amount, line.purchase_price * 3.0)
        self.assertAlmostEqual(report.profit_amount, report.sale_amount - report.cost_amount)

    def test_product_sale_report_sale_origin_sale(self):
        self._create_confirmed_order(2.0, 10.0)
        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.sale_origin, 'sale')

    def test_product_sale_report_sale_origin_pos(self):
        self._create_paid_pos_order(2.0, 10.0, total_cost=8.0)
        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.pos_product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.sale_origin, 'pos')

    def test_product_sale_report_sale_origin_apk(self):
        if 'order_bridge_origin' not in self.env['sale.order']._fields:
            self.skipTest('order_bridge not installed')
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_bridge_origin': 'app',
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'price_unit': 10.0,
            })],
        })
        # order_bridge auto-confirms on create when origin is set
        self.assertEqual(order.state, 'sale')
        report = self.env['bi.product.sale.report'].search([
            ('product_id', '=', self.product.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.sale_origin, 'apk')
