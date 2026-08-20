# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.company_onboarding.wizards.company_onboarding_wizard import TENANT_GROUP_XMLIDS


@tagged('post_install', '-at_install')
class TestProductCompanyIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company'].sudo()
        cls.main_company = cls.env.ref('base.main_company')
        cls.company_a = Company.create({
            'name': 'Isolation Shop A',
            'order_bridge_slug': 'iso-shop-a',
        })
        cls.company_b = Company.create({
            'name': 'Isolation Shop B',
            'order_bridge_slug': 'iso-shop-b',
        })
        group_ids = []
        for xid in TENANT_GROUP_XMLIDS:
            group = cls.env.ref(xid, raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_a = Users.sudo().create({
            'name': 'Shop A Owner',
            'login': 'iso_shop_a_owner',
            'password': 'iso_shop_a_owner',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(6, 0, group_ids)],
        })
        cls.user_b = Users.sudo().create({
            'name': 'Shop B Owner',
            'login': 'iso_shop_b_owner',
            'password': 'iso_shop_b_owner',
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
            'group_ids': [(6, 0, group_ids)],
        })
        Product = cls.env['product.template'].sudo()
        cls.product_main = Product.with_company(cls.main_company).create({
            'name': 'Producto compañía principal',
            'company_id': cls.main_company.id,
            'sale_ok': True,
            'order_bridge_visible': True,
        })
        cls.product_a = Product.with_company(cls.company_a).create({
            'name': 'Producto tienda A',
            'company_id': cls.company_a.id,
            'sale_ok': True,
            'order_bridge_visible': True,
        })
        cls.product_b = Product.with_company(cls.company_b).create({
            'name': 'Producto tienda B',
            'company_id': cls.company_b.id,
            'sale_ok': True,
            'order_bridge_visible': True,
        })

    def _templates_as(self, user, company):
        return self.env['product.template'].with_user(user).with_company(company)

    def test_tenant_create_sets_company_id(self):
        product = self._templates_as(self.user_a, self.company_a).create({
            'name': 'Producto sin compañía explícita',
        })
        self.assertEqual(product.company_id, self.company_a)

    def test_tenant_cannot_see_other_companies_products(self):
        templates_a = self._templates_as(self.user_a, self.company_a)
        self.assertTrue(templates_a.search([('id', '=', self.product_a.id)]))
        self.assertFalse(templates_a.search([('id', '=', self.product_main.id)]))
        self.assertFalse(templates_a.search([('id', '=', self.product_b.id)]))

        templates_b = self._templates_as(self.user_b, self.company_b)
        self.assertTrue(templates_b.search([('id', '=', self.product_b.id)]))
        self.assertFalse(templates_b.search([('id', '=', self.product_a.id)]))
        self.assertFalse(templates_b.search([('id', '=', self.product_main.id)]))

    def test_admin_without_tenant_company_cannot_see_tenant_products(self):
        admin = self.env.ref('base.user_admin')
        admin.invalidate_recordset(['company_ids'])
        self.assertNotIn(self.company_a, admin.company_ids)
        self.assertNotIn(self.company_b, admin.company_ids)
        templates_admin = self._templates_as(admin, self.main_company)
        self.assertFalse(templates_admin.search([('id', '=', self.product_a.id)]))
        self.assertFalse(templates_admin.search([('id', '=', self.product_b.id)]))
        self.assertTrue(templates_admin.search([('id', '=', self.product_main.id)]))

    def test_order_bridge_catalog_domain_excludes_other_company(self):
        variant_a = self.product_a.product_variant_id
        found_in_a = self.env['product.product'].sudo().search(
            self.company_a._order_bridge_product_domain() + [('id', '=', variant_a.id)],
        )
        found_in_b = self.env['product.product'].sudo().search(
            self.company_b._order_bridge_product_domain() + [('id', '=', variant_a.id)],
        )
        self.assertEqual(found_in_a, variant_a)
        self.assertFalse(found_in_b)

    def test_tenant_category_is_isolated_system_category_stays_shared(self):
        categ_a = self.env['product.category'].sudo().with_company(self.company_a).create({
            'name': 'Categoría solo A',
        })
        self.assertEqual(categ_a.company_id, self.company_a)
        categs_b = self.env['product.category'].with_user(self.user_b).with_company(self.company_b)
        self.assertFalse(categs_b.search([('id', '=', categ_a.id)]))
        goods = self.env.ref('product.product_category_goods', raise_if_not_found=False)
        if goods and not goods.company_id:
            self.assertTrue(categs_b.search([('id', '=', goods.id)]))
