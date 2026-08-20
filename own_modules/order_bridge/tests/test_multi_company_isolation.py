# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Multi-company isolation tests for own_modules (single DB, several res.company)."""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiCompanyIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({
            'name': 'Isolation Co A',
            'order_bridge_slug': 'iso-a',
        })
        cls.company_b = Company.create({
            'name': 'Isolation Co B',
            'order_bridge_slug': 'iso-b',
        })
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        group_ids = [
            cls.env.ref('base.group_user').id,
            cls.env.ref('sales_team.group_sale_salesman').id,
            cls.env.ref('order_bridge.group_order_bridge_user').id,
        ]
        if cls.env.ref('bi_analytics.model_bi_other_cost', raise_if_not_found=False):
            # ACL for bi models is on salesman group already
            pass
        cls.user_a = Users.create({
            'name': 'User A',
            'login': 'iso_user_a',
            'password': 'iso_user_a',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(6, 0, group_ids)],
        })
        cls.user_b = Users.create({
            'name': 'User B',
            'login': 'iso_user_b',
            'password': 'iso_user_b',
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
            'group_ids': [(6, 0, group_ids)],
        })

    def test_device_search_isolated(self):
        Device = self.env['order_bridge.device']
        partner_a = self.env['res.partner'].create({
            'name': 'Partner A',
            'company_id': self.company_a.id,
        })
        partner_b = self.env['res.partner'].create({
            'name': 'Partner B',
            'company_id': self.company_b.id,
        })
        Device.create({
            'device_key': 'iso-key-a',
            'partner_id': partner_a.id,
            'company_id': self.company_a.id,
            'phone': '60000001',
        })
        Device.create({
            'device_key': 'iso-key-b',
            'partner_id': partner_b.id,
            'company_id': self.company_b.id,
            'phone': '60000002',
        })
        devices_a = Device.with_user(self.user_a).with_company(self.company_a).search([])
        devices_b = Device.with_user(self.user_b).with_company(self.company_b).search([])
        self.assertEqual(devices_a.mapped('device_key'), ['iso-key-a'])
        self.assertEqual(devices_b.mapped('device_key'), ['iso-key-b'])

    def test_banner_search_isolated(self):
        Banner = self.env['order_bridge.banner']
        Banner.create({
            'title': 'Banner A',
            'company_id': self.company_a.id,
        })
        Banner.create({
            'title': 'Banner B',
            'company_id': self.company_b.id,
        })
        titles_a = Banner.with_user(self.user_a).with_company(self.company_a).search([]).mapped('title')
        titles_b = Banner.with_user(self.user_b).with_company(self.company_b).search([]).mapped('title')
        self.assertEqual(titles_a, ['Banner A'])
        self.assertEqual(titles_b, ['Banner B'])

    def test_bi_other_cost_isolated(self):
        if 'bi.other.cost' not in self.env:
            self.skipTest('bi_analytics not installed')
        category = self.env['bi.cost.category'].search([], limit=1)
        if not category:
            self.skipTest('no bi.cost.category')
        Cost = self.env['bi.other.cost']
        Cost.create({
            'name': 'Cost A',
            'amount': 10.0,
            'category_id': category.id,
            'company_id': self.company_a.id,
            'currency_id': self.company_a.currency_id.id,
        })
        Cost.create({
            'name': 'Cost B',
            'amount': 20.0,
            'category_id': category.id,
            'company_id': self.company_b.id,
            'currency_id': self.company_b.currency_id.id,
        })
        names_a = Cost.with_user(self.user_a).with_company(self.company_a).search([]).mapped('name')
        names_b = Cost.with_user(self.user_b).with_company(self.company_b).search([]).mapped('name')
        self.assertIn('Cost A', names_a)
        self.assertNotIn('Cost B', names_a)
        self.assertIn('Cost B', names_b)
        self.assertNotIn('Cost A', names_b)

    def test_register_scopes_phone_per_company(self):
        Device = self.env['order_bridge.device'].sudo()
        r1 = Device.register_or_get('60011111', 'reg-key-a', company=self.company_a)
        r2 = Device.register_or_get('60011111', 'reg-key-b', company=self.company_b)
        self.assertTrue(r1['device'].active)
        self.assertTrue(r2['device'].active)
        self.assertEqual(r1['device'].company_id, self.company_a)
        self.assertEqual(r2['device'].company_id, self.company_b)
        self.assertEqual(r1['partner'].company_id, self.company_a)
        self.assertEqual(r2['partner'].company_id, self.company_b)

    def test_find_company_by_slug(self):
        found = self.env['res.company']._order_bridge_find_by_slug('iso-a')
        self.assertEqual(found, self.company_a)
        missing = self.env['res.company']._order_bridge_find_by_slug('does-not-exist')
        self.assertFalse(missing)
