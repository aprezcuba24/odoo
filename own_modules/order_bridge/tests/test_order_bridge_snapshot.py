# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.utils.mobile_deliveries import order_to_remote_delivery
from odoo.addons.order_bridge.utils.order_contact import delivery_address_text, order_phone


@tagged('post_install', '-at_install')
class TestOrderBridgeAddressSnapshot(TransactionCase):
    def test_app_order_copies_partner_address_to_snapshot(self):
        company = self.env.company

        partner = self.env['res.partner'].create({
            'name': '+529991234567',
            'phone': '+529991234567',
        })
        mun = self.env['order_bridge.municipality'].create({'name': 'Capital'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': 'Centro',
            'municipality_id': mun.id,
        })
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Avenida 1',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'state': 'MX',
            'latitude': 23.1,
            'longitude': -82.3,
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
        self.assertEqual(snap.neighborhood_id, nbh)
        self.assertEqual(snap.municipality_id, mun)
        self.assertEqual(snap.state, 'MX')
        self.assertEqual(snap.phone, '+529991234567')
        self.assertAlmostEqual(snap.latitude, 23.1, places=5)
        self.assertAlmostEqual(snap.longitude, -82.3, places=5)

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

    def test_neighborhood_unlink_blocked_when_used_in_address(self):
        partner = self.env['res.partner'].create({'name': 'p-unlink', 'phone': '+529990000001'})
        mun = self.env['order_bridge.municipality'].create({'name': 'M-unlink'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': 'B-unlink',
            'municipality_id': mun.id,
        })
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'x',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'state': 's',
        })
        with self.assertRaises(UserError):
            nbh.unlink()

    def _create_order_for_replace(self, key, with_address=True, **address_vals):
        partner = self.env['res.partner'].create({
            'name': f'Cliente {key}',
            'phone': '+529991111111',
        })
        mun = self.env['order_bridge.municipality'].create({'name': f'Mun {key}'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': f'Barrio {key}', 'municipality_id': mun.id,
        })
        address = self.env['order_bridge.partner_address']
        if with_address:
            address = address.create({
                'partner_id': partner.id,
                'street': 'Calle original 1',
                'municipality_id': mun.id,
                'neighborhood_id': nbh.id,
                'state': 'La Habana',
                'latitude': 23.1,
                'longitude': -82.3,
                **address_vals,
            })
        product = self.env['product.product'].create({
            'name': f'Producto {key}', 'sale_ok': True, 'list_price': 10.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 1.0})],
        })
        return order, partner, address

    def test_snapshot_keeps_values_when_customer_changes(self):
        order, partner, address = self._create_order_for_replace('frozen')
        partner.phone = '+529990000000'
        address.write({'street': 'Calle nueva 9', 'latitude': 20.5, 'longitude': -75.5})
        self.assertEqual(order_phone(order), '+529991111111')
        self.assertIn('Calle original 1', delivery_address_text(order))
        payload = order_to_remote_delivery(order)
        self.assertEqual(payload['customerPhone'], '+529991111111')
        self.assertEqual(payload['point'], {'latitude': 23.1, 'longitude': -82.3})

    def test_replace_updates_existing_snapshot_with_current_customer_data(self):
        order, partner, address = self._create_order_for_replace('replace')
        snap = order.order_bridge_snapshot_address_id
        mun2 = self.env['order_bridge.municipality'].create({'name': 'Otro municipio'})
        nbh2 = self.env['order_bridge.neighborhood'].create({
            'name': 'Otro barrio', 'municipality_id': mun2.id,
        })
        partner.phone = '+529990000000'
        address.write({
            'street': 'Calle nueva 9',
            'municipality_id': mun2.id,
            'neighborhood_id': nbh2.id,
            'state': 'Matanzas',
            'latitude': 20.5,
            'longitude': -75.5,
        })
        self.assertIn('Calle original 1', order.order_bridge_order_contact)
        self.assertIn('Calle nueva 9', order.order_bridge_customer_contact)

        order.action_order_bridge_replace_with_customer_address()

        self.assertEqual(order.order_bridge_snapshot_address_id, snap)
        self.assertEqual(snap.street, 'Calle nueva 9')
        self.assertEqual(snap.municipality_id, mun2)
        self.assertEqual(snap.neighborhood_id, nbh2)
        self.assertEqual(snap.state, 'Matanzas')
        self.assertEqual(snap.phone, '+529990000000')
        self.assertAlmostEqual(snap.latitude, 20.5, places=5)
        self.assertAlmostEqual(snap.longitude, -75.5, places=5)
        self.assertEqual(order_phone(order), '+529990000000')
        self.assertIn('Otro barrio. Otro municipio', delivery_address_text(order))
        self.assertEqual(
            order_to_remote_delivery(order)['point'], {'latitude': 20.5, 'longitude': -75.5},
        )
        self.assertIn('Calle nueva 9', order.order_bridge_order_contact)
        # El cliente no se modifica.
        self.assertEqual(partner.phone, '+529990000000')
        self.assertEqual(address.street, 'Calle nueva 9')

    def test_replace_creates_snapshot_when_order_has_none(self):
        order, partner, _address = self._create_order_for_replace('late', with_address=False)
        self.assertFalse(order.order_bridge_snapshot_address_id)
        self.assertIn('no tiene dirección', order.order_bridge_order_contact)
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Calle tardía 3',
            'municipality_id': self.env['order_bridge.municipality'].create({'name': 'Mun tardío'}).id,
            'neighborhood_id': self.env['order_bridge.neighborhood'].create({
                'name': 'Barrio tardío',
                'municipality_id': self.env['order_bridge.municipality'].search(
                    [('name', '=', 'Mun tardío')], limit=1).id,
            }).id,
            'latitude': 22.0,
            'longitude': -80.0,
        })
        order.action_order_bridge_replace_with_customer_address()
        snap = order.order_bridge_snapshot_address_id
        self.assertTrue(snap)
        self.assertEqual(snap.street, 'Calle tardía 3')
        self.assertEqual(snap.phone, '+529991111111')
        self.assertEqual(order_to_remote_delivery(order)['point'], {'latitude': 22.0, 'longitude': -80.0})

    def test_replace_without_customer_address_raises_and_keeps_order(self):
        order, _partner, _address = self._create_order_for_replace('none', with_address=False)
        with self.assertRaises(UserError):
            order.action_order_bridge_replace_with_customer_address()
        self.assertFalse(order.order_bridge_snapshot_address_id)

    def test_replace_without_customer_address_keeps_existing_snapshot(self):
        order, _partner, address = self._create_order_for_replace('keep')
        snap = order.order_bridge_snapshot_address_id
        address.unlink()
        with self.assertRaises(UserError):
            order.action_order_bridge_replace_with_customer_address()
        self.assertEqual(order.order_bridge_snapshot_address_id, snap)
        self.assertEqual(snap.street, 'Calle original 1')
