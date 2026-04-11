# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeAddressSnapshot(TransactionCase):
    def test_app_order_copies_partner_address_to_snapshot(self):
        company = self.env.company

        partner = self.env['res.partner'].create({
            'name': '+529991234567',
            'phone': '+529991234567',
        })
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Avenida 1',
            'neighborhood': 'Centro',
            'municipality': 'Capital',
            'state': 'MX',
        })
        device = self.env['order_bridge.device'].create({
            'device_key': 'snapshot-test-key',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Línea pedido Tienda Apk',
            'sale_ok': True,
            'order_bridge_visible': True,
            'list_price': 10.99,
        })
        product = tmpl.product_variant_id
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'company_id': company.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1.0}),
            ],
        })
        self.assertTrue(order.order_bridge_snapshot_address_id)
        snap = order.order_bridge_snapshot_address_id
        self.assertEqual(snap.street, 'Avenida 1')
        self.assertEqual(snap.neighborhood, 'Centro')
        self.assertEqual(snap.municipality, 'Capital')
        self.assertEqual(snap.state, 'MX')

    def test_app_order_without_saved_address_has_no_snapshot(self):
        company = self.env.company

        partner = self.env['res.partner'].create({
            'name': '+529998765432',
            'phone': '+529998765432',
        })
        device = self.env['order_bridge.device'].create({
            'device_key': 'snapshot-test-key-2',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        tmpl = self.env['product.template'].create({
            'name': 'Línea pedido Tienda Apk 2',
            'sale_ok': True,
            'order_bridge_visible': True,
            'list_price': 5.0,
        })
        product = tmpl.product_variant_id
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'company_id': company.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1.0}),
            ],
        })
        self.assertFalse(order.order_bridge_snapshot_address_id)
