# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOptionalApps(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.optional_app = cls.env.ref(
            'company_onboarding.optional_app_payment_gateway',
        )
        cls.optional_app_merchant_store = cls.env.ref(
            'company_onboarding.optional_app_merchant_store',
        )
        cls.admin = cls.env.ref('base.user_admin')
        cls.company = cls.env['res.company'].sudo().create({
            'name': 'Optional Apps Co',
            'order_bridge_slug': 'optional-apps-co',
        })

    def test_payment_gateway_off_by_default(self):
        self.assertFalse(self.company.has_optional_app('payment_gateway'))
        self.assertNotIn(self.optional_app, self.company.optional_app_ids)

    def test_merchant_store_off_by_default(self):
        self.assertFalse(self.company.has_optional_app('merchant_store'))
        self.assertNotIn(
            self.optional_app_merchant_store,
            self.company.optional_app_ids,
        )

    def test_admin_enter_company_links_without_moving_partner(self):
        self.admin.invalidate_recordset(['company_ids', 'company_id'])
        self.assertNotIn(self.company, self.admin.company_ids)
        partner_company_before = self.admin.partner_id.company_id

        action = self.company.with_user(self.admin).action_enter_company()
        self.assertEqual(action.get('type'), 'ir.actions.client')
        self.assertEqual(action.get('tag'), 'reload')

        self.admin.invalidate_recordset(['company_ids', 'company_id'])
        self.admin.partner_id.invalidate_recordset(['company_id'])
        self.assertIn(self.company, self.admin.company_ids)
        # Main company on the user/partner must stay put (cids handles the UI switch).
        self.assertEqual(self.admin.partner_id.company_id, partner_company_before)

    def test_non_system_cannot_enter_company(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Tenant No Enter',
            'login': 'tenant_no_enter',
            'password': 'tenant_no_enter',
            'company_ids': [Command.set([self.company.id])],
            'company_id': self.company.id,
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.company.with_user(user).action_enter_company()

    def test_stripe_menu_hidden_until_app_enabled(self):
        menu = self.env.ref(
            'payment_gateway.menu_payment_gateway_stripe_account',
            raise_if_not_found=False,
        )
        if not menu:
            self.skipTest('payment_gateway not installed')

        self.company.with_user(self.admin).action_enter_company()
        # Entrar links membership and relies on cids for the active company.
        Menu = self.env(user=self.admin)['ir.ui.menu'].with_context(
            allowed_company_ids=[self.company.id],
        )

        visible_off = Menu._visible_menu_ids(debug=False)
        self.assertNotIn(menu.id, visible_off)

        self.company.sudo().write({
            'optional_app_ids': [Command.link(self.optional_app.id)],
        })
        visible_on = Menu._visible_menu_ids(debug=False)
        self.assertIn(menu.id, visible_on)

    def test_credentials_rejected_when_app_disabled(self):
        if 'payment_gateway.stripe.account' not in self.env:
            self.skipTest('payment_gateway not installed')

        from odoo.addons.payment_gateway.services.secrets import (
            MissingStripeSecrets,
            credentials_for_company,
            payment_gateway_enabled_for_company,
        )

        self.assertFalse(payment_gateway_enabled_for_company(self.company))
        self.env['payment_gateway.stripe.account'].sudo().create({
            'company_id': self.company.id,
            'secret_key': 'sk_test_optional',
            'publishable_key': 'pk_test_optional',
            'webhook_secret': 'whsec_optional',
        })
        with self.assertRaises(MissingStripeSecrets):
            credentials_for_company(self.env, self.company)

        self.company.sudo().write({
            'optional_app_ids': [Command.link(self.optional_app.id)],
        })
        self.assertTrue(payment_gateway_enabled_for_company(self.company))
        creds = credentials_for_company(self.env, self.company)
        self.assertEqual(creds.secret_key, 'sk_test_optional')

    def test_merchant_store_menu_hidden_until_app_enabled(self):
        """Empty root menus have no action yet, so Odoo omits them from
        ``_visible_menu_ids``. Check the optional-app gate directly; point 2+
        will add children with actions and then the Stripe-style assert applies.
        """
        menu = self.env.ref(
            'merchant_store.menu_merchant_store_root',
            raise_if_not_found=False,
        )
        if not menu:
            self.skipTest('merchant_store not installed')

        self.company.with_user(self.admin).action_enter_company()
        Menu = self.env(user=self.admin)['ir.ui.menu'].with_context(
            allowed_company_ids=[self.company.id],
        )

        hidden_off = Menu._optional_app_hidden_menu_ids()
        self.assertIn(menu.id, hidden_off)

        self.company.sudo().write({
            'optional_app_ids': [Command.link(self.optional_app_merchant_store.id)],
        })
        hidden_on = Menu._optional_app_hidden_menu_ids()
        self.assertNotIn(menu.id, hidden_on)
