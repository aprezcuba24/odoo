# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMerchantStoreCheckout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({
            'name': 'Merchant Checkout Co A',
            'order_bridge_slug': 'merchant-checkout-co-a',
        })
        cls.company_b = Company.create({
            'name': 'Merchant Checkout Co B',
            'order_bridge_slug': 'merchant-checkout-co-b',
        })
        Merchant = cls.env['merchant_store.merchant']
        cls.merchant_a = Merchant.create({
            'name': 'Checkout Merchant A',
            'company_id': cls.company_a.id,
        })
        cls.merchant_a2 = Merchant.create({
            'name': 'Checkout Merchant A2',
            'company_id': cls.company_a.id,
        })
        cls.merchant_b = Merchant.create({
            'name': 'Checkout Merchant B',
            'company_id': cls.company_b.id,
        })
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Checkout Customer A',
            'company_id': cls.company_a.id,
        })
        ProductTemplate = cls.env['product.template']
        cls.merchant_product_a = ProductTemplate.with_company(cls.company_a).create({
            'name': 'Checkout producto A',
            'list_price': 20.0,
            'merchant_id': cls.merchant_a.id,
            'sale_ok': True,
        })
        cls.merchant_product_a2 = ProductTemplate.with_company(cls.company_a).create({
            'name': 'Checkout producto A2',
            'list_price': 15.0,
            'merchant_id': cls.merchant_a2.id,
            'sale_ok': True,
        })
        cls.merchant_product_b = ProductTemplate.with_company(cls.company_b).create({
            'name': 'Checkout producto B',
            'list_price': 12.0,
            'merchant_id': cls.merchant_b.id,
            'sale_ok': True,
        })
        cls.own_product_a = ProductTemplate.with_company(cls.company_a).create({
            'name': 'Checkout producto propio',
            'list_price': 10.0,
            'company_id': cls.company_a.id,
            'sale_ok': True,
            'order_bridge_visible': True,
        })

    def _checkout(self, lines, checkout_id='checkout-1', order_bridge_order=None):
        return self.env['sale.order'].merchant_store_checkout(
            self.company_a,
            self.partner_a,
            checkout_id,
            lines,
            order_bridge_order=order_bridge_order,
        )

    def _apk_order(self, company=None, origin='app'):
        company = company or self.company_a
        return self.env['sale.order'].with_company(company).create({
            'partner_id': self.partner_a.id,
            'company_id': company.id,
            'order_bridge_origin': origin,
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 10.0,
            })],
        })

    def test_checkout_splits_by_merchant(self):
        orders = self._checkout([
            {'product_id': self.merchant_product_a.product_variant_id.id, 'qty': 2},
            {'product_id': self.merchant_product_a2.product_variant_id.id, 'qty': 1},
        ])
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders.mapped('client_checkout_id'), ['checkout-1', 'checkout-1'])
        self.assertFalse(any(orders.mapped('order_bridge_origin')))
        self.assertEqual(set(orders.mapped('state')), {'draft'})
        self.assertEqual(set(orders.mapped('order_bridge_store_state')), {'reviewing'})
        self.assertEqual(
            set(orders.mapped('merchant_id')),
            {self.merchant_a, self.merchant_a2},
        )
        by_merchant = {order.merchant_id: order for order in orders}
        self.assertEqual(
            by_merchant[self.merchant_a].order_line.product_id,
            self.merchant_product_a.product_variant_id,
        )
        self.assertEqual(by_merchant[self.merchant_a].order_line.product_uom_qty, 2.0)
        self.assertEqual(
            by_merchant[self.merchant_a2].order_line.product_id,
            self.merchant_product_a2.product_variant_id,
        )

    def test_checkout_idempotent(self):
        first = self._checkout([
            {'product_id': self.merchant_product_a.product_variant_id.id, 'qty': 1},
            {'product_id': self.merchant_product_a2.product_variant_id.id, 'qty': 1},
        ])
        second = self._checkout([
            {'product_id': self.merchant_product_a.product_variant_id.id, 'qty': 9},
        ])
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        total = self.env['sale.order'].search([
            ('company_id', '=', self.company_a.id),
            ('client_checkout_id', '=', 'checkout-1'),
        ])
        self.assertEqual(total, first)

    def test_checkout_rejects_own_product(self):
        with self.assertRaises(UserError):
            self._checkout([
                {'product_id': self.own_product_a.product_variant_id.id, 'qty': 1},
            ])
        self.assertFalse(self.env['sale.order'].search([
            ('client_checkout_id', '=', 'checkout-1'),
            ('company_id', '=', self.company_a.id),
        ]))

    def test_checkout_rejects_other_company_product(self):
        with self.assertRaises(UserError):
            self._checkout([
                {'product_id': self.merchant_product_b.product_variant_id.id, 'qty': 1},
            ])
        self.assertFalse(self.env['sale.order'].search([
            ('client_checkout_id', '=', 'checkout-1'),
            ('company_id', '=', self.company_a.id),
        ]))

    def test_checkout_rejects_empty_lines(self):
        with self.assertRaises(UserError):
            self._checkout([])

    def test_checkout_rejects_empty_checkout_id(self):
        with self.assertRaises(UserError):
            self._checkout(
                [{'product_id': self.merchant_product_a.product_variant_id.id, 'qty': 1}],
                checkout_id='  ',
            )

    def test_checkout_link_leaves_apk_order_untouched(self):
        apk = self._apk_order()
        apk_vals = {
            'order_bridge_origin': apk.order_bridge_origin,
            'company_id': apk.company_id.id,
            'order_bridge_store_state': apk.order_bridge_store_state,
            'merchant_id': apk.merchant_id.id,
            'state': apk.state,
        }
        orders = self._checkout(
            [
                {'product_id': self.merchant_product_a.product_variant_id.id, 'qty': 1},
                {'product_id': self.merchant_product_a2.product_variant_id.id, 'qty': 1},
            ],
            order_bridge_order=apk,
        )
        self.assertEqual(orders.mapped('order_bridge_order_id'), apk)
        apk.invalidate_recordset()
        self.assertEqual(apk.order_bridge_origin, apk_vals['order_bridge_origin'])
        self.assertEqual(apk.company_id.id, apk_vals['company_id'])
        self.assertEqual(apk.order_bridge_store_state, apk_vals['order_bridge_store_state'])
        self.assertFalse(apk.merchant_id)
        self.assertEqual(apk.state, apk_vals['state'])

        sub = orders.filtered(lambda o: o.merchant_id == self.merchant_a)
        sub.action_order_bridge_negotiate()
        self.assertEqual(sub.order_bridge_store_state, 'negotiating')
        apk.invalidate_recordset(['order_bridge_store_state'])
        self.assertEqual(apk.order_bridge_store_state, apk_vals['order_bridge_store_state'])

    def test_checkout_rejects_link_other_company(self):
        apk_b = self.env['sale.order'].with_company(self.company_b).create({
            'partner_id': self.env['res.partner'].create({
                'name': 'Checkout Customer B',
                'company_id': self.company_b.id,
            }).id,
            'company_id': self.company_b.id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({
                'product_id': self.env['product.template'].with_company(
                    self.company_b,
                ).create({
                    'name': 'Own B',
                    'list_price': 5.0,
                    'company_id': self.company_b.id,
                    'sale_ok': True,
                }).product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })
        with self.assertRaises(UserError):
            self._checkout(
                [{'product_id': self.merchant_product_a.product_variant_id.id, 'qty': 1}],
                order_bridge_order=apk_b,
            )

    def test_checkout_rejects_link_merchant_order(self):
        merchant_order = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'merchant_id': self.merchant_a.id,
            'order_line': [Command.create({
                'product_id': self.merchant_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })
        with self.assertRaises(UserError):
            self._checkout(
                [{'product_id': self.merchant_product_a2.product_variant_id.id, 'qty': 1}],
                checkout_id='checkout-link-merchant',
                order_bridge_order=merchant_order,
            )

    def test_checkout_rejects_link_without_origin(self):
        plain = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })
        self.assertFalse(plain.order_bridge_origin)
        with self.assertRaises(UserError):
            self._checkout(
                [{'product_id': self.merchant_product_a.product_variant_id.id, 'qty': 1}],
                checkout_id='checkout-link-plain',
                order_bridge_order=plain,
            )

    def test_checkout_fields_require_merchant(self):
        plain = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })
        with self.assertRaises(ValidationError):
            plain.write({'client_checkout_id': 'no-merchant'})
        apk = self._apk_order()
        with self.assertRaises(ValidationError):
            plain.write({'order_bridge_order_id': apk.id})

    def test_manual_suborder_without_checkout_still_ok(self):
        order = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'merchant_id': self.merchant_a.id,
            'order_line': [Command.create({
                'product_id': self.merchant_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })
        self.assertFalse(order.client_checkout_id)
        self.assertFalse(order.order_bridge_order_id)
