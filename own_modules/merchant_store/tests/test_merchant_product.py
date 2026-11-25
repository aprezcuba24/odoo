# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


def _action_domain(action):
    return literal_eval(action.domain or '[]')


@tagged('post_install', '-at_install')
class TestMerchantStoreProduct(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({
            'name': 'Merchant Product Co A',
            'order_bridge_slug': 'merchant-product-co-a',
        })
        cls.company_b = Company.create({
            'name': 'Merchant Product Co B',
            'order_bridge_slug': 'merchant-product-co-b',
        })
        Merchant = cls.env['merchant_store.merchant']
        cls.merchant_a = Merchant.create({
            'name': 'Merchant A',
            'company_id': cls.company_a.id,
        })
        cls.merchant_b = Merchant.create({
            'name': 'Merchant B',
            'company_id': cls.company_b.id,
        })

    def test_create_merchant_product_isolation(self):
        product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Producto comerciante',
            'list_price': 12.5,
            'merchant_id': self.merchant_a.id,
            'order_bridge_visible': True,
            'available_in_pos': True,
        })
        self.assertEqual(product.merchant_id, self.merchant_a)
        self.assertEqual(product.company_id, self.company_a)
        self.assertEqual(product.list_price, 12.5)
        self.assertFalse(product.order_bridge_visible)
        self.assertFalse(product.available_in_pos)
        self.assertTrue(product.active)

    def test_write_keeps_isolation_flags(self):
        product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Producto flags',
            'merchant_id': self.merchant_a.id,
        })
        product.write({
            'name': 'Producto flags 2',
            'order_bridge_visible': True,
            'available_in_pos': True,
        })
        self.assertFalse(product.order_bridge_visible)
        self.assertFalse(product.available_in_pos)
        self.assertEqual(product.company_id, self.company_a)

    def test_catalog_domain_excludes_merchant_products(self):
        own = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Producto propio',
            'company_id': self.company_a.id,
            'order_bridge_visible': True,
            'sale_ok': True,
        })
        merchant_product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Producto comerciante catálogo',
            'merchant_id': self.merchant_a.id,
            'sale_ok': True,
        })
        # Even if someone forces visibility in SQL, domain must exclude by merchant_id.
        self.env.cr.execute(
            'UPDATE product_template SET order_bridge_visible = TRUE WHERE id = %s',
            (merchant_product.id,),
        )
        merchant_product.invalidate_recordset(['order_bridge_visible'])

        domain = self.company_a._order_bridge_product_domain()
        Product = self.env['product.product'].sudo()
        found_own = Product.search(domain + [('product_tmpl_id', '=', own.id)])
        found_merchant = Product.search(
            domain + [('product_tmpl_id', '=', merchant_product.id)]
        )
        self.assertEqual(found_own, own.product_variant_id)
        self.assertFalse(found_merchant)
        self.assertIn(('product_tmpl_id.merchant_id', '=', False), domain)

    def test_merchant_assignment_aligns_company(self):
        product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Sin comerciante',
            'company_id': self.company_a.id,
            'order_bridge_visible': True,
        })
        product.write({
            'merchant_id': self.merchant_b.id,
            'company_id': self.company_a.id,
            'order_bridge_visible': True,
            'available_in_pos': True,
        })
        self.assertEqual(product.merchant_id, self.merchant_b)
        self.assertEqual(product.company_id, self.company_b)
        self.assertFalse(product.order_bridge_visible)
        self.assertFalse(product.available_in_pos)

    def test_check_company_rejects_mismatched_merchant(self):
        product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Mismatch',
            'merchant_id': self.merchant_a.id,
        })
        self.env.cr.execute(
            'UPDATE product_template SET company_id = %s WHERE id = %s',
            (self.company_b.id, product.id),
        )
        product.invalidate_recordset(['company_id'])
        with self.assertRaises(UserError):
            product._check_company()

    def test_sale_and_pos_actions_exclude_merchant_products(self):
        sale_action = self.env.ref('sale.product_template_action')
        pos_action = self.env.ref('point_of_sale.product_template_action_pos_product')
        variant_action = self.env.ref('product.product_normal_action_sell')

        sale_domain = _action_domain(sale_action)
        pos_domain = _action_domain(pos_action)
        variant_domain = _action_domain(variant_action)
        self.assertIn(('merchant_id', '=', False), sale_domain)
        self.assertIn(('merchant_id', '=', False), pos_domain)
        self.assertIn(('product_tmpl_id.merchant_id', '=', False), variant_domain)

        merchant_product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Solo Comercios',
            'merchant_id': self.merchant_a.id,
        })
        own = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Solo Ventas',
            'company_id': self.company_a.id,
        })

        ProductTemplate = self.env['product.template'].with_company(self.company_a)
        self.assertTrue(ProductTemplate.search(sale_domain + [('id', '=', own.id)]))
        self.assertFalse(
            ProductTemplate.search(sale_domain + [('id', '=', merchant_product.id)])
        )
        self.assertFalse(
            ProductTemplate.search(pos_domain + [('id', '=', merchant_product.id)])
        )

    def test_merchant_store_product_action_lists_only_merchant_products(self):
        action = self.env.ref('merchant_store.action_merchant_store_product_template')
        merchant_product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'En Comercios',
            'merchant_id': self.merchant_a.id,
        })
        own = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Fuera Comercios',
            'company_id': self.company_a.id,
        })
        domain = _action_domain(action)
        ProductTemplate = self.env['product.template'].with_company(self.company_a)
        self.assertTrue(
            ProductTemplate.search(domain + [('id', '=', merchant_product.id)])
        )
        self.assertFalse(ProductTemplate.search(domain + [('id', '=', own.id)]))

    def test_product_menu_exists(self):
        menu = self.env.ref('merchant_store.menu_merchant_store_product')
        self.assertEqual(menu.name, 'Productos')
        self.assertEqual(
            menu.action,
            self.env.ref('merchant_store.action_merchant_store_product_template'),
        )

    def test_stock_actions_exclude_merchant_products(self):
        stock_tmpl_action = self.env.ref('stock.product_template_action_product')
        stock_variant_action = self.env.ref('stock.stock_product_normal_action')

        tmpl_domain = _action_domain(stock_tmpl_action)
        variant_domain = _action_domain(stock_variant_action)
        self.assertIn(('merchant_id', '=', False), tmpl_domain)
        self.assertIn(('product_tmpl_id.merchant_id', '=', False), variant_domain)

        merchant_product = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Solo Comercios Stock',
            'merchant_id': self.merchant_a.id,
        })
        own = self.env['product.template'].with_company(self.company_a).create({
            'name': 'Propio Stock',
            'company_id': self.company_a.id,
        })

        ProductTemplate = self.env['product.template'].with_company(self.company_a)
        ProductProduct = self.env['product.product'].with_company(self.company_a)
        self.assertTrue(ProductTemplate.search(tmpl_domain + [('id', '=', own.id)]))
        self.assertFalse(
            ProductTemplate.search(tmpl_domain + [('id', '=', merchant_product.id)])
        )
        self.assertTrue(
            ProductProduct.search(variant_domain + [('id', '=', own.product_variant_id.id)])
        )
        self.assertFalse(
            ProductProduct.search(
                variant_domain + [('id', '=', merchant_product.product_variant_id.id)]
            )
        )

    def test_merchant_store_product_search_view_filters_by_merchant(self):
        action = self.env.ref('merchant_store.action_merchant_store_product_template')
        search_view = self.env.ref(
            'merchant_store.view_merchant_store_product_template_search'
        )
        self.assertEqual(action.search_view_id, search_view)
        arch = search_view.arch_db or ''
        self.assertIn('name="merchant_id"', arch)
        self.assertIn('group_by', arch)
        self.assertIn('<searchpanel>', arch)
