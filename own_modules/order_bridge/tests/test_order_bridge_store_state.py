# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeStoreState(TransactionCase):
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

        order.order_bridge_store_state = 'delivered'

        for p in pickings:
            self.assertEqual(p.state, 'done')
