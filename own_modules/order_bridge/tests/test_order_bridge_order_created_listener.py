# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock

from odoo.addons.order_bridge.models import sale_order as sale_order_module
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeOrderCreatedListener(TransactionCase):
    def _patch_order_created_listener(self):
        mock_listener = MagicMock()
        SaleOrder = sale_order_module.SaleOrder
        original = SaleOrder._LISTENERS
        SaleOrder._LISTENERS = [
            (mock_listener, 'order_bridge_order_created'),
            *[(fn, name) for fn, name in original if name != 'order_bridge_order_created'],
        ]
        return mock_listener, original, SaleOrder

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

    def test_order_created_listener_called_for_app_origin(self):
        mock_listener, original, SaleOrder = self._patch_order_created_listener()
        try:
            order = self._create_app_order()
            mock_listener.assert_called_once()
            call_order, old_entity, new_entity = mock_listener.call_args[0]
            self.assertEqual(call_order, order)
            self.assertIsNone(old_entity)
            self.assertEqual(new_entity, order)
        finally:
            SaleOrder._LISTENERS = original

    def test_order_created_listener_not_called_for_admin_origin(self):
        mock_listener, original, SaleOrder = self._patch_order_created_listener()
        try:
            partner = self.env['res.partner'].create({'name': 'Admin test'})
            self.env['sale.order'].create({
                'partner_id': partner.id,
                'order_bridge_origin': 'admin',
            })
            mock_listener.assert_not_called()
        finally:
            SaleOrder._LISTENERS = original

    def test_order_created_listener_not_called_without_bridge_origin(self):
        mock_listener, original, SaleOrder = self._patch_order_created_listener()
        try:
            partner = self.env['res.partner'].create({'name': 'Std sale test'})
            self.env['sale.order'].create({'partner_id': partner.id})
            mock_listener.assert_not_called()
        finally:
            SaleOrder._LISTENERS = original
