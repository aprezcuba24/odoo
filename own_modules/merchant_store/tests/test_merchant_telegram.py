# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.merchant_store.utils.telegram_merchant_message import (
    format_merchant_order_created_message,
)
from odoo.addons.order_bridge.utils.telegram_order_message import format_order_created_message


@tagged('post_install', '-at_install')
class TestMerchantStoreTelegramNotification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Merchant Telegram Co',
            'order_bridge_slug': 'merchant-telegram-co',
        })
        Merchant = cls.env['merchant_store.merchant']
        cls.merchant_a = Merchant.create({
            'name': 'Panadería López',
            'company_id': cls.company.id,
        })
        cls.merchant_b = Merchant.create({
            'name': 'Ferretería *Sur*',
            'company_id': cls.company.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Yiselis Cruz',
            'phone': '+5355512345',
            'company_id': cls.company.id,
        })
        mun = cls.env['order_bridge.municipality'].create({'name': 'Boyeros'})
        nbh = cls.env['order_bridge.neighborhood'].create({
            'name': 'Altahabana',
            'municipality_id': mun.id,
        })
        cls.env['order_bridge.partner_address'].create({
            'partner_id': cls.partner.id,
            'street': 'Calle 3ra',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
        })
        ProductTemplate = cls.env['product.template'].with_company(cls.company)
        cls.product_a = ProductTemplate.create({
            'name': 'Pan artesanal',
            'list_price': 50.0,
            'merchant_id': cls.merchant_a.id,
            'sale_ok': True,
        })
        cls.product_b = ProductTemplate.create({
            'name': 'Martillo *acero*',
            'list_price': 120.0,
            'merchant_id': cls.merchant_b.id,
            'sale_ok': True,
        })
        cls.own_product = ProductTemplate.create({
            'name': 'Arroz tienda',
            'list_price': 80.0,
            'company_id': cls.company.id,
            'sale_ok': True,
            'order_bridge_visible': True,
        })

    def _run_callbacks(self, callbacks):
        with (
            patch('odoo.addons.merchant_store.models.sale_order.send_message') as mock_send,
            patch('odoo.addons.merchant_store.models.sale_order.api.Environment') as mock_env,
            patch('odoo.addons.merchant_store.models.sale_order.Registry') as mock_registry,
        ):
            mock_cr = MagicMock()
            mock_registry.return_value.cursor.return_value.__enter__.return_value = mock_cr
            mock_registry.return_value.cursor.return_value.__exit__.return_value = False
            mock_env.return_value = self.env
            for cb in callbacks:
                cb()
            return mock_send.call_args_list

    def test_format_merchant_message_distinct_from_store_message(self):
        orders = self.env['sale.order'].merchant_store_checkout(
            self.company,
            self.partner,
            'tg-checkout-single',
            [{'product_id': self.product_a.product_variant_id.id, 'qty': 2}],
        )
        self.assertEqual(len(orders), 1)
        order = orders[0]
        text = format_merchant_order_created_message(order)
        self.assertIn('*🏪 Compra en comercio*', text)
        self.assertNotIn('*🛒 Nueva orden*', text)
        self.assertIn('*Comercio:* Panadería López', text)
        self.assertIn(f'*Orden:* {order.name}', text)
        self.assertNotIn('*Pedido de la tienda:*', text)
        self.assertIn('*Cliente:* Yiselis Cruz', text)
        self.assertIn('*Teléfono:* +5355512345', text)
        self.assertIn('Altahabana. Boyeros', text)
        self.assertIn('*Productos de este comercio*', text)
        self.assertIn('Pan artesanal', text)
        self.assertIn('*Total de este comercio:*', text)

    def test_checkout_two_merchants_sends_two_separate_messages(self):
        before = len(self.env.cr.postcommit._funcs)
        orders = self.env['sale.order'].merchant_store_checkout(
            self.company,
            self.partner,
            'tg-checkout-two-merchants',
            [
                {'product_id': self.product_a.product_variant_id.id, 'qty': 2},
                {'product_id': self.product_b.product_variant_id.id, 'qty': 1},
            ],
        )
        self.assertEqual(len(orders), 2)
        new_callbacks = list(self.env.cr.postcommit._funcs)[before:]
        self.assertEqual(len(new_callbacks), 2)

        calls = self._run_callbacks(new_callbacks)
        self.assertEqual(len(calls), 2)

        texts = [call[0][0] for call in calls]
        msg_a = next(t for t in texts if 'Panadería López' in t)
        msg_b = next(t for t in texts if r'Ferretería \*Sur\*' in t)

        self.assertIn('Pan artesanal', msg_a)
        self.assertNotIn('Martillo', msg_a)
        self.assertIn(r'Martillo \*acero\*', msg_b)
        self.assertNotIn('Pan artesanal', msg_b)

    def test_mixed_checkout_keeps_store_and_merchant_messages_separate(self):
        store_order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'order_bridge_origin': 'app',
            'order_line': [
                Command.create({
                    'product_id': self.own_product.product_variant_id.id,
                    'product_uom_qty': 1.0,
                }),
            ],
        })
        merchant_orders = self.env['sale.order'].merchant_store_checkout(
            self.company,
            self.partner,
            'tg-checkout-mixed',
            [{'product_id': self.product_a.product_variant_id.id, 'qty': 2}],
            order_bridge_order=store_order,
        )
        self.assertEqual(len(merchant_orders), 1)
        merchant_order = merchant_orders[0]

        store_text = format_order_created_message(store_order)
        merchant_text = format_merchant_order_created_message(merchant_order)

        self.assertIn('*🛒 Nueva orden*', store_text)
        self.assertIn('Arroz tienda', store_text)
        self.assertNotIn('Pan artesanal', store_text)

        self.assertIn('*🏪 Compra en comercio*', merchant_text)
        self.assertIn(f'*Pedido de la tienda:* {store_order.name}', merchant_text)
        self.assertIn('Pan artesanal', merchant_text)
        self.assertNotIn('Arroz tienda', merchant_text)

    def test_idempotent_checkout_does_not_schedule_duplicate_notification(self):
        before_first = len(self.env.cr.postcommit._funcs)
        self.env['sale.order'].merchant_store_checkout(
            self.company,
            self.partner,
            'tg-checkout-idempotent',
            [{'product_id': self.product_a.product_variant_id.id, 'qty': 1}],
        )
        after_first = len(self.env.cr.postcommit._funcs)
        self.assertEqual(after_first, before_first + 1)

        self.env['sale.order'].merchant_store_checkout(
            self.company,
            self.partner,
            'tg-checkout-idempotent',
            [{'product_id': self.product_a.product_variant_id.id, 'qty': 1}],
        )
        self.assertEqual(len(self.env.cr.postcommit._funcs), after_first)

    def test_manual_merchant_suborder_does_not_schedule_notification(self):
        before = len(self.env.cr.postcommit._funcs)
        self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'merchant_id': self.merchant_a.id,
            'company_id': self.company.id,
            'order_line': [
                Command.create({
                    'product_id': self.product_a.product_variant_id.id,
                    'product_uom_qty': 1.0,
                }),
            ],
        })
        self.assertEqual(len(self.env.cr.postcommit._funcs), before)
