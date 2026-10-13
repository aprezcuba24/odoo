# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.order_bridge.utils import order_stock


@tagged('post_install', '-at_install')
class TestOrderBridgePosStock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('point_of_sale.group_pos_manager')
        cls.partner = cls.env['res.partner'].create({'name': 'OB POS Stock Customer'})
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        assert cls.warehouse, 'company must have a warehouse'

        cls.pos_location = cls.warehouse.pos_type_id.default_location_src_id
        assert cls.pos_location, 'POS picking type must have a source location'
        cls.other_location = cls.env['stock.location'].create({
            'name': 'OB Other Shelf',
            'location_id': cls.warehouse.lot_stock_id.id,
            'usage': 'internal',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'OB POS Storable',
            'sale_ok': True,
            'available_in_pos': True,
            'is_storable': True,
            'list_price': 10.0,
            'taxes_id': False,
        })
        cls.service = cls.env['product.product'].create({
            'name': 'OB POS Service',
            'type': 'service',
            'sale_ok': True,
            'available_in_pos': True,
            'list_price': 5.0,
            'taxes_id': False,
        })
        cls.non_storable = cls.env['product.product'].create({
            'name': 'OB POS Non Storable',
            'sale_ok': True,
            'available_in_pos': True,
            'is_storable': False,
            'list_price': 8.0,
            'taxes_id': False,
        })

        cls.pos_payment_method = cls.env['pos.payment.method'].create({
            'name': 'OB POS Cash',
            'receivable_account_id': cls.env.company.account_default_pos_receivable_account_id.id,
            'journal_id': cls.env['account.journal'].create({
                'name': 'OB POS Bank',
                'code': 'OBPB',
                'type': 'bank',
                'company_id': cls.env.company.id,
            }).id,
        })
        cls.pos_config = cls.env['pos.config'].create({
            'name': 'OB POS Stock Config',
            'payment_method_ids': [Command.set(cls.pos_payment_method.ids)],
            'warehouse_id': cls.warehouse.id,
            'picking_type_id': cls.warehouse.pos_type_id.id,
        })
        cls.env.company.point_of_sale_update_stock_quantities = 'real'

    def _set_location_qty(self, product, location, qty):
        Quant = self.env['stock.quant'].with_context(inventory_mode=True)
        Quant.create({
            'product_id': product.id,
            'location_id': location.id,
            'inventory_quantity': qty,
        }).action_apply_inventory()

    def _location_qty(self, product, location):
        return sum(self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ]).mapped('quantity'))

    def _reserve_via_apk(self, product, qty):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'warehouse_id': self.warehouse.id,
            'order_bridge_origin': 'admin',
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': product.list_price,
            })],
        })
        self.assertEqual(order.state, 'sale')
        return order

    def _create_paid_pos_order(self, product, qty, price_unit=None):
        if not self.pos_config.current_session_id:
            self.pos_config.open_ui()
        price_unit = price_unit if price_unit is not None else product.list_price
        amount = price_unit * qty
        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.pos_config.current_session_id.id,
            'amount_total': amount,
            'amount_tax': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'lines': [Command.create({
                'product_id': product.id,
                'qty': qty,
                'price_unit': price_unit,
                'price_subtotal': abs(amount),
                'price_subtotal_incl': abs(amount),
            })],
        })
        payment_context = {'active_ids': order.ids, 'active_id': order.id}
        payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'payment_method_id': self.pos_payment_method.id,
            'amount': amount,
        })
        payment.with_context(**payment_context).check()
        return order

    def test_check_shortage_when_apk_reserved_on_pos_location(self):
        self._set_location_qty(self.product, self.pos_location, 5.0)
        self._reserve_via_apk(self.product, 5.0)
        self.assertAlmostEqual(
            order_stock.location_free_qty(self.env, self.product, self.pos_location),
            0.0,
        )

        result = self.env['pos.order'].order_bridge_check_pos_stock(
            self.pos_config.id,
            [{'product_id': self.product.id, 'qty': 1.0}],
        )
        self.assertFalse(result['ok'])
        self.assertEqual(result['products'][0]['product_id'], self.product.id)
        self.assertAlmostEqual(result['products'][0]['available_qty'], 0.0)

    def test_check_ignores_stock_only_on_other_location(self):
        """Stock on another location does not count for the POS source location."""
        self._set_location_qty(self.product, self.other_location, 10.0)
        self.assertAlmostEqual(
            self.product.with_context(warehouse_id=self.warehouse.id).free_qty,
            10.0,
        )
        self.assertAlmostEqual(
            order_stock.location_free_qty(self.env, self.product, self.pos_location),
            0.0,
        )

        result = self.env['pos.order'].order_bridge_check_pos_stock(
            self.pos_config.id,
            [{'product_id': self.product.id, 'qty': 1.0}],
        )
        self.assertFalse(result['ok'])
        self.assertAlmostEqual(result['products'][0]['available_qty'], 0.0)

    def test_sell_more_than_pos_location_free_raises_and_keeps_quant(self):
        """5 on POS location + 30 elsewhere: selling 6 is rejected; no -1 on source."""
        self._set_location_qty(self.product, self.pos_location, 5.0)
        self._set_location_qty(self.product, self.other_location, 30.0)

        result = self.env['pos.order'].order_bridge_check_pos_stock(
            self.pos_config.id,
            [{'product_id': self.product.id, 'qty': 6.0}],
        )
        self.assertFalse(result['ok'])
        self.assertAlmostEqual(result['products'][0]['available_qty'], 5.0)

        with self.assertRaises(UserError):
            self._create_paid_pos_order(self.product, 6.0)

        self.assertAlmostEqual(self._location_qty(self.product, self.pos_location), 5.0)
        self.assertAlmostEqual(self._location_qty(self.product, self.other_location), 30.0)

    def test_sell_exact_free_on_pos_location_deducts_source_only(self):
        self._set_location_qty(self.product, self.pos_location, 5.0)
        self._set_location_qty(self.product, self.other_location, 30.0)

        order = self._create_paid_pos_order(self.product, 5.0)
        self.assertIn(order.state, ('paid', 'done', 'invoiced'))

        self.assertAlmostEqual(self._location_qty(self.product, self.pos_location), 0.0)
        self.assertAlmostEqual(self._location_qty(self.product, self.other_location), 30.0)
        self.assertAlmostEqual(
            order_stock.location_free_qty(self.env, self.product, self.pos_location),
            0.0,
        )

        moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.product)
        self.assertTrue(moves)
        self.assertTrue(all(m.location_id == self.pos_location for m in moves))

    def test_paid_pos_order_deducts_from_pos_source_location_only(self):
        self._set_location_qty(self.product, self.pos_location, 10.0)
        self._set_location_qty(self.product, self.other_location, 4.0)
        self._reserve_via_apk(self.product, 3.0)

        free_on_pos = order_stock.location_free_qty(
            self.env, self.product, self.pos_location,
        )
        self.assertGreaterEqual(free_on_pos, 2.0)

        order = self._create_paid_pos_order(self.product, 2.0)
        self.assertIn(order.state, ('paid', 'done', 'invoiced'))

        self.assertAlmostEqual(
            order_stock.location_free_qty(self.env, self.product, self.pos_location),
            free_on_pos - 2.0,
        )
        self.assertAlmostEqual(self._location_qty(self.product, self.other_location), 4.0)

        moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.product)
        self.assertTrue(moves)
        self.assertTrue(all(m.location_id == self.pos_location for m in moves))

    def test_refund_allowed_with_zero_free_qty(self):
        self._set_location_qty(self.product, self.pos_location, 1.0)
        paid = self._create_paid_pos_order(self.product, 1.0)
        self.assertIn(paid.state, ('paid', 'done', 'invoiced'))

        free = order_stock.location_free_qty(self.env, self.product, self.pos_location)
        if free > 0:
            self._reserve_via_apk(self.product, free)

        refund = self._create_paid_pos_order(self.product, -1.0, price_unit=10.0)
        self.assertIn(refund.state, ('paid', 'done', 'invoiced'))

    def test_check_allows_service_and_non_storable(self):
        result = self.env['pos.order'].order_bridge_check_pos_stock(
            self.pos_config.id,
            [
                {'product_id': self.service.id, 'qty': 100.0},
                {'product_id': self.non_storable.id, 'qty': 100.0},
            ],
        )
        self.assertTrue(result['ok'])

    def test_check_ok_when_pos_location_covers_request(self):
        self._set_location_qty(self.product, self.pos_location, 4.0)
        result = self.env['pos.order'].order_bridge_check_pos_stock(
            self.pos_config.id,
            [{'product_id': self.product.id, 'qty': 3.0}],
        )
        self.assertTrue(result['ok'])
