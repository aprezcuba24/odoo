# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.payment_gateway.services.currency import (
    UnsupportedStripeCurrency,
    assert_stripe_currency,
    order_currency_code,
    to_stripe_minor_units,
)


@tagged('post_install', '-at_install')
class TestStripeCurrency(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Cliente moneda Stripe',
            'phone': '+529991110088',
        })
        tmpl = self.env['product.template'].create({
            'name': 'Producto moneda Stripe',
            'sale_ok': True,
            'list_price': 50.0,
            'taxes_id': [Command.clear()],
        })
        self.product = tmpl.product_variant_id
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 50.0,
                'tax_ids': [Command.clear()],
            })],
        })

    def test_assert_accepts_usd_and_eur(self):
        self.assertEqual(assert_stripe_currency('USD'), 'usd')
        self.assertEqual(assert_stripe_currency('eur'), 'eur')

    def test_assert_rejects_cup_empty_and_unknown(self):
        with self.assertRaises(UnsupportedStripeCurrency):
            assert_stripe_currency('CUP')
        with self.assertRaises(UnsupportedStripeCurrency):
            assert_stripe_currency('')
        with self.assertRaises(UnsupportedStripeCurrency):
            assert_stripe_currency(None)
        with self.assertRaises(UnsupportedStripeCurrency):
            assert_stripe_currency('zzz')

    def test_order_currency_code_with_company_currency(self):
        code = order_currency_code(self.order)
        self.assertEqual(code, assert_stripe_currency(self.order.currency_id.name))

    def test_order_currency_code_rejects_unsupported(self):
        # Force a currency name that Stripe does not present (CUP).
        cup = self.env['res.currency'].with_context(active_test=False).search(
            [('name', '=', 'CUP')], limit=1,
        )
        if not cup:
            cup = self.env['res.currency'].create({
                'name': 'CUP',
                'symbol': '₱',
                'rounding': 0.01,
                'position': 'before',
                'active': True,
            })
        else:
            cup.active = True
        self.order.currency_id = cup
        with self.assertRaises(UnsupportedStripeCurrency):
            order_currency_code(self.order)

    def test_to_stripe_minor_units_usd_and_jpy(self):
        self.assertEqual(to_stripe_minor_units(10.50, 'usd'), 1050)
        self.assertEqual(to_stripe_minor_units(1000, 'jpy'), 1000)

    def test_to_stripe_minor_units_special_and_three_decimal(self):
        self.assertEqual(to_stripe_minor_units(10.50, 'isk'), 1050)
        self.assertEqual(to_stripe_minor_units(10.50, 'ugx'), 1050)
        self.assertEqual(to_stripe_minor_units(10.125, 'bhd'), 10130)
