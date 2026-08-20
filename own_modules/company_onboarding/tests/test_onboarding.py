# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged


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
        self.assertTrue(user.has_group('stock.group_stock_manager'))
        self.assertTrue(user.has_group('product.group_product_manager'))
        self.assertTrue(user.has_group('point_of_sale.group_pos_manager'))
        self.assertTrue(user.has_group('account.group_account_invoice'))
        self.assertTrue(user.company_id.chart_template)
        self.assertTrue(
            self.env['pos.config'].search_count([
                ('company_id', '=', user.company_id.id),
            ]),
        )
        product = self.env['product.template'].with_user(user).with_company(user.company_id).create({
            'name': 'Producto onboarding',
        })
        self.assertTrue(product.id)
        self.assertEqual(product.company_id, user.company_id)
        admin = self.env.ref('base.user_admin')
        admin.invalidate_recordset(['company_ids'])
        self.assertNotIn(user.company_id, admin.company_ids)
        settings = self.env['order_bridge.general_settings'].search([
            ('company_id', '=', user.company_id.id),
        ], limit=1)
        self.assertTrue(settings)
        self.assertEqual(settings.shop_phone, '55512345')

        wiz2 = self.env['company.onboarding.wizard'].with_user(user).create({
            'company_name': 'Otra Tienda',
            'order_bridge_slug': 'otra-tienda',
            'country_id': user.company_id.country_id.id,
            'currency_id': user.company_id.currency_id.id,
        })
        with self.assertRaises(UserError):
            wiz2.action_create_company()

    def test_company_partner_gets_spanish_lang(self):
        self.env['res.lang']._activate_lang('es_ES')
        company = self.env['res.company'].sudo().create({
            'name': 'Lang Test Co',
            'order_bridge_slug': 'lang-test-co',
        })
        self.assertEqual(company.partner_id.lang, 'es_ES')

    def test_company_create_does_not_fail_without_spanish(self):
        """If es_ES is not active, company creation must not crash."""
        company = self.env['res.company'].sudo().create({
            'name': 'No Spanish Co',
            'order_bridge_slug': 'no-spanish-co',
        })
        self.assertTrue(company.id)

    def test_signup_user_gets_spanish_lang(self):
        self.env['res.lang']._activate_lang('es_ES')
        Users = self.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({
            'name': 'Signup Lang',
            'login': 'signup_lang_test',
            'password': 'signup_lang_test',
            'company_onboarding_state': 'pending',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        wiz = self.env['company.onboarding.wizard'].with_user(user).create({
            'company_name': 'Spanish Shop',
            'order_bridge_slug': 'spanish-shop',
            'country_id': self.env.company.country_id.id or self.env.ref('base.us').id,
            'currency_id': self.env.company.currency_id.id,
        })
        wiz.action_create_company()
        user.invalidate_recordset()
        self.assertEqual(user.company_id.partner_id.lang, 'es_ES')

    def test_wizard_does_not_overwrite_user_lang(self):
        """The wizard must not change a user's lang if already set."""
        self.env['res.lang']._activate_lang('es_ES')
        Users = self.env['res.users'].with_context(no_reset_password=True)
        user = Users.create({
            'name': 'Keep Lang',
            'login': 'keep_lang_test',
            'password': 'keep_lang_test',
            'lang': 'en_US',
            'company_onboarding_state': 'pending',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        wiz = self.env['company.onboarding.wizard'].with_user(user).create({
            'company_name': 'Keep Lang Shop',
            'order_bridge_slug': 'keep-lang-shop',
            'country_id': self.env.company.country_id.id or self.env.ref('base.us').id,
            'currency_id': self.env.company.currency_id.id,
        })
        wiz.action_create_company()
        user.invalidate_recordset()
        self.assertEqual(user.lang, 'en_US')


@tagged('post_install', '-at_install')
class TestCompanyOnboardingHttp(HttpCase):
    def _create_pending_user(self, login):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login,
            'login': login,
            'password': login,
            'company_onboarding_state': 'pending',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })

    def test_pending_user_is_gated_to_company_form(self):
        self._create_pending_user('pending_http_gate')
        self.authenticate('pending_http_gate', 'pending_http_gate')
        res = self.url_open('/odoo')
        self.assertEqual(res.status_code, 200)
        self.assertIn('/web/onboarding/company', res.url)
        self.assertIn('name="company_name"', res.text)
        self.assertIn('Paso 2 de 2', res.text)
        self.assertIn('Crear compañía', res.text)

    def test_onboarding_post_creates_one_company_then_enters_app(self):
        user = self._create_pending_user('pending_http_post')
        self.authenticate('pending_http_post', 'pending_http_post')
        country_id = self.env.company.country_id.id or self.env.ref('base.us').id
        currency_id = self.env.company.currency_id.id
        payload = {
            'company_name': 'Tienda Http',
            'order_bridge_slug': 'tienda-http-onboard',
            'phone': '5559999',
            'country_id': str(country_id),
            'currency_id': str(currency_id),
            'csrf_token': http.Request.csrf_token(self),
        }
        res = self.url_open('/web/onboarding/company', data=payload)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('/web/onboarding/company', res.url)
        self.assertIn('/odoo', res.url)

        user.invalidate_recordset()
        self.assertEqual(user.company_onboarding_state, 'done')
        self.assertEqual(user.company_id.name, 'Tienda Http')
        self.assertEqual(user.company_ids, user.company_id)
        self.assertEqual(
            self.env['res.company'].search_count([
                ('order_bridge_slug', '=', 'tienda-http-onboard'),
            ]),
            1,
        )

        res_second = self.url_open('/web/onboarding/company', data=payload)
        self.assertNotIn('/web/onboarding/company', res_second.url)
        self.assertEqual(
            self.env['res.company'].search_count([
                ('order_bridge_slug', '=', 'tienda-http-onboard'),
            ]),
            1,
        )

        res_app = self.url_open('/odoo')
        self.assertEqual(res_app.status_code, 200)
        self.assertNotIn('/web/onboarding/company', res_app.url)
