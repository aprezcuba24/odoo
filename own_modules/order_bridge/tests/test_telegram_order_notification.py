# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.addons.order_bridge.listeners import order_created_listener as listener_module
from odoo.addons.order_bridge.utils import telegram_client as telegram_client_module
from odoo.addons.order_bridge.utils.telegram_client import escape_markdown
from odoo.addons.order_bridge.utils.telegram_order_message import format_order_created_message
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeTelegramOrderNotification(TransactionCase):
    def setUp(self):
        super().setUp()
        telegram_client_module._config_warned = False

    def test_escape_markdown(self):
        self.assertEqual(escape_markdown('plain'), 'plain')
        self.assertEqual(escape_markdown('a*b_c`d[e'), r'a\*b\_c\`d\[e')

    def _create_order_with_snapshot(self, **order_vals):
        partner = self.env['res.partner'].create({
            'name': 'Yiselis Cruz',
            'phone': '+5355512345',
        })
        mun = self.env['order_bridge.municipality'].create({'name': 'Boyeros'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': 'Altahabana',
            'municipality_id': mun.id,
        })
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Calle 3ra entre calle A y calle B',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
        })
        device = self.env['order_bridge.device'].create({
            'device_key': 'telegram-notify-test',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        product_a = self.env['product.product'].create({
            'name': 'Leche en polvo Malibú (1kg)',
            'sale_ok': True,
            'list_price': 2400.0,
        })
        product_b = self.env['product.product'].create({
            'name': 'Aceite *especial*',
            'sale_ok': True,
            'list_price': 950.0,
        })
        defaults = {
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [
                Command.create({'product_id': product_a.id, 'product_uom_qty': 1.0}),
                Command.create({'product_id': product_b.id, 'product_uom_qty': 2.0}),
            ],
        }
        defaults.update(order_vals)
        return self.env['sale.order'].create(defaults)

    @patch('odoo.addons.order_bridge.listeners.order_created_listener.send_message')
    def test_format_order_created_message(self, _mock_send):
        order = self._create_order_with_snapshot()
        text = format_order_created_message(order)
        self.assertIn('*🛒 Nueva orden*', text)
        self.assertIn('*Orden de compra:*', text)
        self.assertIn(order.name, text)
        self.assertIn('*Cliente:* Yiselis Cruz', text)
        self.assertIn('*Teléfono:* +5355512345', text)
        self.assertIn('Altahabana. Boyeros', text)
        self.assertIn('*Productos*', text)
        self.assertIn('Leche en polvo Malibú (1kg)', text)
        self.assertIn(r'Aceite \*especial\*', text)
        self.assertIn('*Total:*', text)
        self.assertNotIn('*Cupón de descuento:*', text)

    @patch('odoo.addons.order_bridge.listeners.order_created_listener.send_message')
    def test_format_order_created_message_excludes_description_sale(self, _mock_send):
        product = self.env['product.product'].create({
            'name': 'Arroz',
            'description_sale': 'Descripción larga del producto',
            'sale_ok': True,
            'list_price': 100.0,
        })
        partner = self.env['res.partner'].create({
            'name': 'Cliente Arroz',
            'phone': '+5355512345',
        })
        device = self.env['order_bridge.device'].create({
            'device_key': 'telegram-desc-test',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1.0}),
            ],
        })
        text = format_order_created_message(order)
        self.assertIn('Arroz', text)
        self.assertNotIn('Descripción larga del producto', text)

    def _create_promo_program(self, code='TEST10', discount=10):
        self.env['loyalty.program'].search([]).sudo().write({'active': False})
        return self.env['loyalty.program'].create({
            'name': 'Telegram promo test',
            'program_type': 'promo_code',
            'applies_on': 'current',
            'trigger': 'with_code',
            'rule_ids': [(0, 0, {'mode': 'with_code', 'code': code})],
            'reward_ids': [(0, 0, {
                'reward_type': 'discount',
                'discount': discount,
                'discount_mode': 'percent',
                'discount_applicability': 'order',
                'required_points': 1,
            })],
        })

    @patch('odoo.addons.order_bridge.listeners.order_created_listener.send_message')
    def test_format_order_created_message_with_promo_code(self, _mock_send):
        self._create_promo_program()
        product = self.env['product.product'].create({
            'name': 'Producto con cupón',
            'sale_ok': True,
            'list_price': 100.0,
            'taxes_id': [(6, 0, [])],
        })
        partner = self.env['res.partner'].create({
            'name': 'Cliente Cupón',
            'phone': '+5355512345',
        })
        device = self.env['order_bridge.device'].create({
            'device_key': 'telegram-promo-test',
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        order = self.env['sale.order'].with_context(
            order_bridge_promo_code='TEST10',
        ).create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1.0}),
            ],
        })
        text = format_order_created_message(order)
        self.assertIn('*Cupón de descuento:* TEST10', text)
        self.assertIn('*Descuento:*', text)
        self.assertIn('*Total:*', text)
        self.assertEqual(order.amount_total, 90.0)
        self.assertEqual(order.order_bridge_promo_code, 'TEST10')

    @patch.dict(os.environ, {}, clear=True)
    def test_send_message_without_env_warns_once(self):
        with self.assertLogs('odoo.addons.order_bridge.utils.telegram_client', level='WARNING') as logs:
            self.assertFalse(telegram_client_module.send_message('test'))
            self.assertFalse(telegram_client_module.send_message('test'))
        warning_logs = [line for line in logs.output if 'Telegram omitido' in line]
        self.assertEqual(len(warning_logs), 1)

    @patch.dict(
        os.environ,
        {'TELEGRAM_BOT_TOKEN': 'test-token', 'TELEGRAM_CHAT_ID': '-100123'},
        clear=True,
    )
    @patch('odoo.addons.order_bridge.utils.telegram_client.urllib.request.urlopen')
    def test_send_message_with_env_posts_markdown(self, mock_urlopen):
        @contextmanager
        def fake_urlopen(_req, timeout=15):
            _ = timeout
            yield MagicMock(read=lambda: json.dumps({'ok': True}).encode('utf-8'))

        mock_urlopen.side_effect = fake_urlopen
        self.assertTrue(telegram_client_module.is_configured())
        with patch.object(telegram_client_module._logger, 'info') as mock_info:
            ok = telegram_client_module.send_message('*bold* text', order_ref='O-TEST')
        self.assertTrue(ok)
        mock_info.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode('utf-8'))
        self.assertEqual(payload['parse_mode'], 'Markdown')
        self.assertEqual(payload['chat_id'], '-100123')
        self.assertEqual(payload['text'], '*bold* text')

    @patch.dict(
        os.environ,
        {'TELEGRAM_BOT_TOKEN': 'test-token', 'TELEGRAM_CHAT_ID': '123'},
        clear=True,
    )
    @patch('odoo.addons.order_bridge.listeners.order_created_listener.send_message')
    def test_listener_sends_telegram_for_app_order(self, mock_send):
        from odoo.addons.order_bridge.listeners.order_created_listener import order_bridge_order_created

        mock_send.return_value = True
        order = self._create_order_with_snapshot()
        order_bridge_order_created(order, None, order)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][0]
        self.assertIn(order.name, text)
        self.assertEqual(mock_send.call_args.kwargs.get('order_ref'), order.name)

    @patch.dict(os.environ, {}, clear=True)
    @patch('odoo.addons.order_bridge.listeners.order_created_listener.send_message')
    def test_listener_skips_non_app_origin(self, mock_send):
        partner = self.env['res.partner'].create({'name': 'Admin'})
        self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'admin',
        })
        mock_send.assert_not_called()

    def test_listener_module_calls_send_message(self):
        order = MagicMock()
        order.order_bridge_origin = 'app'
        order.order_bridge_ref = 'O-MOCK'
        order.name = 'S-MOCK'
        with patch.object(listener_module, 'send_message', return_value=True) as mock_send:
            with patch.object(
                listener_module,
                'format_order_created_message',
                return_value='msg',
            ) as mock_format:
                listener_module.order_bridge_order_created(order, None, order)
        mock_format.assert_called_once_with(order)
        mock_send.assert_called_once_with('msg', order_ref='S-MOCK')
