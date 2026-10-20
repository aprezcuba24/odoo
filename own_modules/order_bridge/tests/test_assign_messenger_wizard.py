# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.utils.constant import (
    STATE_READY_FOR_DELIVERY,
    STATE_REVIEWING,
)


@tagged('post_install', '-at_install')
class TestAssignMessengerWizard(TransactionCase):
    def _create_store_order(self, *, phone, store_state=STATE_READY_FOR_DELIVERY):
        partner = self.env['res.partner'].create({
            'name': f'Cliente {phone}',
            'phone': phone,
        })
        mun = self.env['order_bridge.municipality'].create({'name': f'Mun {phone}'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': f'Barrio {phone}',
            'municipality_id': mun.id,
        })
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Calle 1',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'state': 'La Habana',
        })
        product = self.env['product.product'].create({
            'name': f'Producto {phone}',
            'sale_ok': True,
            'list_price': 10.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1}),
            ],
        })
        if store_state != STATE_REVIEWING:
            order.write({'order_bridge_store_state': store_state})
        return order

    def test_assign_messenger_to_selected_ready_orders(self):
        order_a = self._create_store_order(phone='+53555004001')
        order_b = self._create_store_order(phone='+53555004002')
        messenger = self.env['order_bridge.messenger'].create({
            'name': 'Mensajero Lote',
            'company_id': order_a.company_id.id,
        })
        wizard = self.env['order_bridge.assign.messenger.wizard'].with_context(
            active_model='sale.order',
            active_ids=(order_a | order_b).ids,
        ).create({
            'messenger_id': messenger.id,
        })
        self.assertEqual(wizard.order_count, 2)
        result = wizard.action_assign()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        self.assertTrue(result['infos']['assigned'])
        self.assertEqual(result['infos']['count'], 2)
        self.assertEqual(result['infos']['messenger_name'], 'Mensajero Lote')
        self.assertEqual(order_a.order_bridge_messenger_id, messenger)
        self.assertEqual(order_b.order_bridge_messenger_id, messenger)

    def test_assign_messenger_rejects_reviewing_order(self):
        ready = self._create_store_order(phone='+53555004011')
        reviewing = self._create_store_order(
            phone='+53555004012',
            store_state=STATE_REVIEWING,
        )
        messenger = self.env['order_bridge.messenger'].create({
            'name': 'Mensajero Rechazo',
            'company_id': ready.company_id.id,
        })
        wizard = self.env['order_bridge.assign.messenger.wizard'].with_context(
            active_model='sale.order',
            active_ids=(ready | reviewing).ids,
        ).create({
            'messenger_id': messenger.id,
        })
        with self.assertRaises(UserError):
            wizard.action_assign()
        self.assertFalse(ready.order_bridge_messenger_id)
        self.assertFalse(reviewing.order_bridge_messenger_id)
