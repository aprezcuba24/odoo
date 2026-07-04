# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock, patch

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.listeners import store_state_push_listener as push_listener_module
from odoo.addons.order_bridge.utils.push_order_message import format_store_state_push


@tagged('post_install', '-at_install')
class TestOrderBridgeStoreStatePushListener(TransactionCase):
    def _create_app_order(self):
        partner = self.env['res.partner'].create({'name': 'Push test', 'phone': '+52999001122'})
        device = self.env['order_bridge.device'].create({
            'device_key': 'store-state-push-listener-test',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        product = self.env['product.product'].create({
            'name': 'Producto push test',
            'sale_ok': True,
            'list_price': 1.0,
        })
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 1.0})],
        })

    def test_format_store_state_push(self):
        order = self._create_app_order()
        order.write({'order_bridge_store_state': 'negotiating'})
        title, body, data = format_store_state_push(order)
        self.assertIn(order.name, title)
        self.assertIn('Negociando', body)
        self.assertEqual(data, {'type': 'order_status', 'order_id': str(order.id)})

    @patch.object(push_listener_module, '_schedule_store_state_push')
    def test_write_store_state_schedules_push(self, mock_schedule):
        order = self._create_app_order()
        order.write({'order_bridge_store_state': 'negotiating'})
        mock_schedule.assert_called_once_with(order)

    @patch.object(push_listener_module, '_schedule_store_state_push')
    def test_write_without_store_state_change_does_not_schedule(self, mock_schedule):
        order = self._create_app_order()
        order.write({'note': 'solo nota interna'})
        mock_schedule.assert_not_called()

    @patch.object(push_listener_module, '_schedule_store_state_push')
    def test_no_push_without_bridge_origin(self, mock_schedule):
        partner = self.env['res.partner'].create({'name': 'Std sale push test'})
        order = self.env['sale.order'].create({'partner_id': partner.id})
        order.write({'order_bridge_store_state': 'negotiating'})
        mock_schedule.assert_not_called()

    def test_schedule_registers_postcommit_callback(self):
        order = self._create_app_order()
        before = len(self.env.cr.postcommit._funcs)
        push_listener_module._schedule_store_state_push(order)
        self.assertEqual(len(self.env.cr.postcommit._funcs), before + 1)

    @patch(
        'odoo.addons.order_bridge.models.fcm.OrderBridgeFcm.send_to_partner',
        return_value={'sent_batches': 1, 'token_count': 1},
    )
    @patch('odoo.addons.order_bridge.listeners.store_state_push_listener.api.Environment')
    @patch('odoo.addons.order_bridge.listeners.store_state_push_listener.Registry')
    def test_postcommit_callback_sends_fcm(
        self, mock_registry, mock_environment, mock_send,
    ):
        order = self._create_app_order()
        before = len(self.env.cr.postcommit._funcs)
        order.write({'order_bridge_store_state': 'negotiating'})
        self.assertGreater(len(self.env.cr.postcommit._funcs), before)
        callback = self.env.cr.postcommit._funcs[-1]

        mock_cr = MagicMock()
        mock_registry.return_value.cursor.return_value.__enter__.return_value = mock_cr
        mock_registry.return_value.cursor.return_value.__exit__.return_value = False
        mock_environment.return_value = self.env

        callback()
        mock_send.assert_called_once()
        _args, kwargs = mock_send.call_args
        self.assertEqual(_args[0], order.partner_id.id)
        self.assertEqual(kwargs['data'], {'type': 'order_status', 'order_id': str(order.id)})
