# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.float_utils import float_is_zero


@tagged('post_install', '-at_install')
class TestOrderBridgeStoreState(TransactionCase):
    def _ob_goto_delivered(self, order):
        """Estado tienda: reviewing → ready_for_delivery → delivered (transiciones válidas)."""
        order.write({'order_bridge_store_state': 'ready_for_delivery'})
        order.write({'order_bridge_store_state': 'delivered'})

    def _ob_create_storable_order(self, qty=2.0, device_key='store-state-ob-temp'):
        company = self.env.company
        partner = self.env['res.partner'].create({
            'name': '+529991112200',
            'phone': '+529991112200',
        })
        device = self.env['order_bridge.device'].create({
            'device_key': device_key,
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto order bridge state test',
            'sale_ok': True,
            'order_bridge_visible': True,
            'is_storable': True,
            'list_price': 10.0,
        })
        product = tmpl.product_variant_id
        wh = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        self.assertTrue(wh)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': wh.lot_stock_id.id,
            'inventory_quantity': 20.0,
        }).action_apply_inventory()
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'company_id': company.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': qty})],
        })
        return order, product

    def test_delivered_validates_outgoing_pickings(self):
        company = self.env.company
        partner = self.env['res.partner'].create({
            'name': '+529991112233',
            'phone': '+529991112233',
        })
        device = self.env['order_bridge.device'].create({
            'device_key': 'store-state-picking-test',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto estado tienda entregado',
            'sale_ok': True,
            'order_bridge_visible': True,
            'is_storable': True,
            'list_price': 10.0,
        })
        product = tmpl.product_variant_id
        wh = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        self.assertTrue(wh)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': wh.lot_stock_id.id,
            'inventory_quantity': 10.0,
        }).action_apply_inventory()

        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'company_id': company.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 2.0})],
        })
        self.assertEqual(order.state, 'sale')
        pickings = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
        self.assertTrue(pickings)
        self.assertTrue(all(p.state != 'done' for p in pickings))

        self._ob_goto_delivered(order)

        for p in pickings:
            self.assertEqual(p.state, 'done')

    def test_canceled_cancels_order_and_outgoing_pickings(self):
        order, _product = self._ob_create_storable_order(device_key='store-state-canceled-ok')
        self.assertEqual(order.state, 'sale')
        pickings = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
        self.assertTrue(pickings)
        self.assertTrue(all(p.state in ('draft', 'waiting', 'confirmed', 'assigned') for p in pickings))

        order.write({'order_bridge_store_state': 'canceled'})

        self.assertEqual(order.state, 'cancel')
        for p in pickings:
            self.assertEqual(p.state, 'cancel')

    def test_canceled_rejected_when_delivered_storable(self):
        order, _product = self._ob_create_storable_order(device_key='store-state-canceled-reject')
        self._ob_goto_delivered(order)
        line = order.order_line.filtered(lambda l: l.product_id and l.product_id.is_storable)[:1]
        self.assertTrue(line)
        self.assertGreater(line.qty_delivered, 0.0, 'La entrega validada debe dejar cantidad entregada neta > 0')

        with self.assertRaises(UserError) as em:
            order.write({'order_bridge_store_state': 'canceled'})
        self.assertIn('devoluciones', em.exception.args[0].lower())
        self.assertEqual(order.state, 'sale')

    def test_canceled_after_full_return(self):
        order, _product = self._ob_create_storable_order(device_key='store-state-canceled-return')
        self._ob_goto_delivered(order)
        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing' and p.state == 'done',
        )[:1]
        self.assertTrue(outgoing)

        return_wiz = self.env['stock.return.picking'].with_context(
            active_id=outgoing.id,
            active_model='stock.picking',
        ).create({})
        for ret_line in return_wiz.product_return_moves:
            ret_line.quantity = 2.0
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

        line = order.order_line.filtered(lambda l: l.product_id and l.product_id.is_storable)[:1]
        self.assertTrue(line)
        self.assertTrue(
            float_is_zero(line.qty_delivered, precision_rounding=line.product_uom_id.rounding),
        )

        order.write({'order_bridge_store_state': 'canceled'})
        self.assertEqual(order.state, 'cancel')

    def test_invalid_store_transition_raises(self):
        order, _product = self._ob_create_storable_order(device_key='store-state-invalid-tr')
        with self.assertRaises(UserError):
            order.write({'order_bridge_store_state': 'delivered'})

    def test_action_order_bridge_negotiate(self):
        order, _product = self._ob_create_storable_order(device_key='store-state-act-neg')
        order.action_order_bridge_negotiate()
        self.assertEqual(order.order_bridge_store_state, 'negotiating')

    def test_action_order_bridge_ready_then_delivered(self):
        order, _product = self._ob_create_storable_order(device_key='store-state-act-del')
        order.action_order_bridge_ready_for_delivery()
        self.assertEqual(order.order_bridge_store_state, 'ready_for_delivery')
        order.action_order_bridge_delivered()
        self.assertEqual(order.order_bridge_store_state, 'delivered')

    def test_action_order_bridge_cancel_store(self):
        order, _product = self._ob_create_storable_order(device_key='store-state-act-can')
        order.action_order_bridge_cancel_store()
        self.assertEqual(order.order_bridge_store_state, 'canceled')
        self.assertEqual(order.state, 'cancel')
