# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCompanyOnboarding(TransactionCase):
    def test_wizard_creates_company_and_assigns_user(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({
            'name': 'Pending Owner',
            'login': 'pending_owner',
            'password': 'pending_owner',
            'company_onboarding_state': 'pending',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        wiz = self.env['company.onboarding.wizard'].with_user(user).create({
            'company_name': 'Tienda Nueva',
            'order_bridge_slug': 'tienda-nueva',
            'country_id': self.env.company.country_id.id or self.env.ref('base.us').id,
            'currency_id': self.env.company.currency_id.id,
            'phone': '55512345',
        })
        wiz.action_create_company()
        user.invalidate_recordset()
        self.assertEqual(user.company_onboarding_state, 'done')
        self.assertEqual(user.company_id.name, 'Tienda Nueva')
        self.assertEqual(user.company_ids, user.company_id)
        self.assertEqual(user.company_id.order_bridge_slug, 'tienda-nueva')
        self.assertFalse(user.has_group('base.group_system'))
        self.assertFalse(user.has_group('base.group_multi_company'))
        self.assertTrue(user.has_group('order_bridge.group_order_bridge_manager'))
        settings = self.env['order_bridge.general_settings'].search([
            ('company_id', '=', user.company_id.id),
        ], limit=1)
        self.assertTrue(settings)
        self.assertEqual(settings.shop_phone, '55512345')
