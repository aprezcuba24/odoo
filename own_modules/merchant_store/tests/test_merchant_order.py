# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.sql import SQL


def _action_domain(action):
    return literal_eval(action.domain or '[]')


@tagged('post_install', '-at_install')
class TestMerchantStoreOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({
            'name': 'Merchant Order Co A',
            'order_bridge_slug': 'merchant-order-co-a',
        })
        cls.company_b = Company.create({
            'name': 'Merchant Order Co B',
            'order_bridge_slug': 'merchant-order-co-b',
        })
        Merchant = cls.env['merchant_store.merchant']
        cls.merchant_a = Merchant.create({
            'name': 'Order Merchant A',
            'company_id': cls.company_a.id,
        })
        cls.merchant_a2 = Merchant.create({
            'name': 'Order Merchant A2',
            'company_id': cls.company_a.id,
        })
        cls.merchant_b = Merchant.create({
            'name': 'Order Merchant B',
            'company_id': cls.company_b.id,
        })
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Merchant Order Customer A',
            'company_id': cls.company_a.id,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Merchant Order Customer B',
            'company_id': cls.company_b.id,
        })
        ProductTemplate = cls.env['product.template']
        cls.merchant_product_a = ProductTemplate.with_company(cls.company_a).create({
            'name': 'Producto comerciante A',
            'list_price': 20.0,
            'merchant_id': cls.merchant_a.id,
            'sale_ok': True,
        })
        cls.merchant_product_a2 = ProductTemplate.with_company(cls.company_a).create({
            'name': 'Producto comerciante A2',
            'list_price': 15.0,
            'merchant_id': cls.merchant_a2.id,
            'sale_ok': True,
        })
        cls.own_product_a = ProductTemplate.with_company(cls.company_a).create({
            'name': 'Producto propio A',
            'list_price': 10.0,
            'company_id': cls.company_a.id,
            'sale_ok': True,
        })
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        group_user = cls.env.ref('merchant_store.group_merchant_store_user')
        group_base = cls.env.ref('base.group_user')
        cls.user_a = Users.create({
            'name': 'Merchant Order User A',
            'login': 'merchant_order_user_a',
            'password': 'merchant_order_user_a',
            'company_id': cls.company_a.id,
            'company_ids': [Command.set([cls.company_a.id])],
            'group_ids': [Command.set([group_base.id, group_user.id])],
        })

    def _create_suborder(self, merchant, partner, product_tmpl, company=None):
        company = company or merchant.company_id
        return self.env['sale.order'].with_company(company).create({
            'partner_id': partner.id,
            'merchant_id': merchant.id,
            'order_line': [Command.create({
                'product_id': product_tmpl.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': product_tmpl.list_price,
            })],
        })

    def test_create_suborder_isolation(self):
        order = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        self.assertEqual(order.merchant_id, self.merchant_a)
        self.assertEqual(order.company_id, self.company_a)
        self.assertFalse(order.order_bridge_origin)
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.order_bridge_store_state, 'reviewing')

    def test_store_state_transitions(self):
        order = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        other = self._create_suborder(
            self.merchant_a2, self.partner_a, self.merchant_product_a2,
        )
        order.action_order_bridge_negotiate()
        self.assertEqual(order.order_bridge_store_state, 'negotiating')
        self.assertEqual(other.order_bridge_store_state, 'reviewing')

        order.action_order_bridge_ready_for_delivery()
        self.assertEqual(order.order_bridge_store_state, 'ready_for_delivery')
        order.action_order_bridge_delivered()
        self.assertEqual(order.order_bridge_store_state, 'delivered')

        invalid = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        with self.assertRaises(UserError):
            invalid.write({'order_bridge_store_state': 'delivered'})

    def test_action_confirm_rejected(self):
        order = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')

    def test_line_same_merchant_ok(self):
        order = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(
            order.order_line.product_id.product_tmpl_id.merchant_id,
            self.merchant_a,
        )

    def test_line_own_product_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['sale.order'].with_company(self.company_a).create({
                'partner_id': self.partner_a.id,
                'merchant_id': self.merchant_a.id,
                'order_line': [Command.create({
                    'product_id': self.own_product_a.product_variant_id.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 10.0,
                })],
            })

    def test_line_other_merchant_product_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['sale.order'].with_company(self.company_a).create({
                'partner_id': self.partner_a.id,
                'merchant_id': self.merchant_a.id,
                'order_line': [Command.create({
                    'product_id': self.merchant_product_a2.product_variant_id.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 15.0,
                })],
            })

    def test_merchant_product_on_own_order_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['sale.order'].with_company(self.company_a).create({
                'partner_id': self.partner_a.id,
                'order_line': [Command.create({
                    'product_id': self.merchant_product_a.product_variant_id.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 20.0,
                })],
            })

    def test_actions_domains(self):
        suborder = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        own_order = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 10.0,
            })],
        })
        apk_order = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'order_bridge_origin': 'admin',
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 10.0,
            })],
        })

        merchant_action = self.env.ref('merchant_store.action_merchant_store_sale_order')
        sale_orders = self.env.ref('sale.action_orders')
        sale_quotations = self.env.ref('sale.action_quotations')
        sale_quotations_onboarding = self.env.ref('sale.action_quotations_with_onboarding')
        apk_action = self.env.ref('order_bridge.action_order_bridge_sale_orders')

        merchant_domain = _action_domain(merchant_action)
        orders_domain = _action_domain(sale_orders)
        quotations_domain = _action_domain(sale_quotations)
        quotations_onboarding_domain = _action_domain(sale_quotations_onboarding)
        apk_domain = _action_domain(apk_action)

        self.assertIn(('merchant_id', '!=', False), merchant_domain)
        self.assertIn(('merchant_id', '=', False), orders_domain)
        self.assertIn(('merchant_id', '=', False), quotations_domain)
        self.assertIn(('merchant_id', '=', False), quotations_onboarding_domain)
        self.assertIn(('order_bridge_origin', '!=', False), apk_domain)

        SaleOrder = self.env['sale.order'].with_company(self.company_a)
        self.assertTrue(SaleOrder.search(merchant_domain + [('id', '=', suborder.id)]))
        self.assertFalse(SaleOrder.search(merchant_domain + [('id', '=', own_order.id)]))
        self.assertFalse(SaleOrder.search(orders_domain + [('id', '=', suborder.id)]))
        self.assertTrue(SaleOrder.search(orders_domain + [('id', '=', own_order.id)]))
        self.assertFalse(SaleOrder.search(quotations_domain + [('id', '=', suborder.id)]))
        self.assertFalse(SaleOrder.search(apk_domain + [('id', '=', suborder.id)]))
        self.assertTrue(SaleOrder.search(apk_domain + [('id', '=', apk_order.id)]))

    def test_order_menu_exists(self):
        menu = self.env.ref('merchant_store.menu_merchant_store_order')
        self.assertEqual(menu.name, 'Pedidos')
        self.assertEqual(
            menu.action,
            self.env.ref('merchant_store.action_merchant_store_sale_order'),
        )

    def test_sale_report_excludes_merchant_orders(self):
        suborder = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        own_order = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 10.0,
            })],
        })
        Report = self.env['sale.report'].with_company(self.company_a)
        self.assertFalse(Report.search([('name', '=', suborder.name)]))
        self.assertTrue(Report.search([('name', '=', own_order.name)]))

    def test_bi_product_sale_report_excludes_merchant_orders(self):
        suborder = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        own_order = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 2.0,
                'price_unit': 10.0,
            })],
        })
        own_order.action_confirm()
        self.env.cr.execute(
            'UPDATE sale_order SET state = %s WHERE id = %s',
            ('sale', suborder.id),
        )
        suborder.invalidate_recordset(['state'])

        Report = self.env['bi.product.sale.report']
        self.assertFalse(Report.search([
            ('order_ref', '=', suborder.name),
            ('company_id', '=', self.company_a.id),
        ]))
        self.assertTrue(Report.search([
            ('order_ref', '=', own_order.name),
            ('company_id', '=', self.company_a.id),
        ]))

    def test_profitability_sql_extra_excludes_merchant(self):
        Report = self.env['bi.profitability.report']
        extra = Report._sale_order_sql_extra()
        self.assertIsInstance(extra, SQL)
        self.assertIn('merchant_id IS NULL', str(extra))

    def test_company_isolation_read(self):
        order_b = self.env['sale.order'].with_company(self.company_b).create({
            'partner_id': self.partner_b.id,
            'merchant_id': self.merchant_b.id,
            'order_line': [Command.create({
                'product_id': self.env['product.template'].with_company(
                    self.company_b,
                ).create({
                    'name': 'Producto comerciante B',
                    'list_price': 8.0,
                    'merchant_id': self.merchant_b.id,
                    'sale_ok': True,
                }).product_variant_id.id,
                'product_uom_qty': 1.0,
                'price_unit': 8.0,
            })],
        })
        found = self.env['sale.order'].with_user(self.user_a).with_company(
            self.company_a,
        ).search([('id', '=', order_b.id)])
        self.assertFalse(found)

    def test_new_order_can_select_registered_merchant(self):
        form = self.env.ref('merchant_store.view_merchant_store_sale_order_form')
        arch = form.arch_db or ''
        self.assertIn("('company_id', 'in', allowed_company_ids)", arch)
        order = self.env['sale.order'].new({
            'partner_id': self.partner_a.id,
            'company_id': self.company_a.id,
        })
        order.merchant_id = self.merchant_b
        order._onchange_merchant_id_company()
        self.assertEqual(order.company_id, self.company_b)
        self.assertFalse(order.order_bridge_origin)

    def test_store_state_buttons_visibility(self):
        form = self.env.ref('merchant_store.view_merchant_store_sale_order_form')
        Users = self.env['res.users'].with_context(no_reset_password=True)
        group_base = self.env.ref('base.group_user')
        group_salesman = self.env.ref('sales_team.group_sale_salesman')
        group_account_readonly = self.env.ref('account.group_account_readonly')

        salesman = Users.create({
            'name': 'Merchant Order Salesman',
            'login': 'merchant_order_salesman',
            'password': 'merchant_order_salesman',
            'company_id': self.company_a.id,
            'company_ids': [Command.set([self.company_a.id])],
            'group_ids': [Command.set([group_base.id, group_salesman.id])],
        })
        plain_user = Users.create({
            'name': 'Merchant Order Plain User',
            'login': 'merchant_order_plain_user',
            'password': 'merchant_order_plain_user',
            'company_id': self.company_a.id,
            'company_ids': [Command.set([self.company_a.id])],
            'group_ids': [Command.set([group_base.id, group_account_readonly.id])],
        })

        salesman_arch = self.env['sale.order'].with_user(salesman).get_view(
            view_id=form.id, view_type='form',
        )['arch']
        plain_arch = self.env['sale.order'].with_user(plain_user).get_view(
            view_id=form.id, view_type='form',
        )['arch']

        for action_name in (
            'action_order_bridge_negotiate',
            'action_order_bridge_ready_for_delivery',
            'action_order_bridge_delivered',
            'action_order_bridge_cancel_store',
        ):
            self.assertIn(action_name, salesman_arch)
            self.assertNotIn(action_name, plain_arch)

    @patch('odoo.addons.merchant_store.models.sale_order._schedule_store_state_push')
    def test_store_state_change_schedules_push(self, mock_schedule):
        order = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        order.action_order_bridge_negotiate()
        mock_schedule.assert_called_once_with(order)

    @patch('odoo.addons.merchant_store.models.sale_order._schedule_store_state_push')
    def test_write_without_store_state_change_does_not_schedule_push(self, mock_schedule):
        order = self._create_suborder(
            self.merchant_a, self.partner_a, self.merchant_product_a,
        )
        order.write({'note': 'nota interna'})
        mock_schedule.assert_not_called()

