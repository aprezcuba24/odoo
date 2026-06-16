# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock, patch

from odoo.addons.order_bridge.models import sale_order as sale_order_module
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeOrderCreatedListener(TransactionCase):
    def _create_app_order(self):
        partner = self.env['res.partner'].create({'name': 'Test', 'phone': '+52999001122'})
        device = self.env['order_bridge.device'].create({
            'device_key': 'order-created-listener-test',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        product = self.env['product.product'].create({
            'name': 'Producto listener test',
            'sale_ok': True,
            'list_price': 1.0,
        })
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 1.0})],
        })

    @patch.object(
        sale_order_module.SaleOrder,
        '_order_bridge_schedule_order_created_notification',
    )
    def test_create_schedules_notification_for_app_origin(self, mock_schedule):
        self._create_app_order()
        mock_schedule.assert_called_once()

    @patch.object(
        sale_order_module.SaleOrder,
        '_order_bridge_schedule_order_created_notification',
    )
    def test_create_does_not_schedule_for_admin_origin(self, mock_schedule):
        partner = self.env['res.partner'].create({'name': 'Admin test'})
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'admin',
        })
        mock_schedule.assert_not_called()

    @patch.object(
        sale_order_module.SaleOrder,
        '_order_bridge_schedule_order_created_notification',
    )
    def test_create_does_not_schedule_without_bridge_origin(self, mock_schedule):
        partner = self.env['res.partner'].create({'name': 'Std sale test'})
        self.env['sale.order'].create({'partner_id': partner.id})
        mock_schedule.assert_not_called()

    def test_schedule_registers_postcommit_callback(self):
        order = self._create_app_order()
        before = len(self.env.cr.postcommit._funcs)
        order._order_bridge_schedule_order_created_notification()
        self.assertEqual(len(self.env.cr.postcommit._funcs), before + 1)

    @patch('odoo.addons.order_bridge.listeners.order_created_listener.send_message')
    @patch('odoo.addons.order_bridge.models.sale_order.api.Environment')
    @patch('odoo.addons.order_bridge.models.sale_order.Registry')
    def test_schedule_postcommit_callback_dispatches_event(
        self, mock_registry, mock_environment, mock_send,
    ):
        order = self._create_app_order()
        before = len(self.env.cr.postcommit._funcs)
        order._order_bridge_schedule_order_created_notification()
        self.assertEqual(len(self.env.cr.postcommit._funcs), before + 1)
        callback = self.env.cr.postcommit._funcs[-1]

        mock_cr = MagicMock()
        mock_registry.return_value.cursor.return_value.__enter__.return_value = mock_cr
        mock_registry.return_value.cursor.return_value.__exit__.return_value = False
        mock_env = self.env
        mock_environment.return_value = mock_env

        callback()
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs.get('order_ref'), order.order_bridge_ref)
