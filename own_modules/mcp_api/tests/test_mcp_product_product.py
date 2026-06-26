# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase


@tagged('post_install', '-at_install')
class TestMcpApiProductProduct(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categ_bebidas = cls.env['product.category'].create({'name': 'Bebidas MCP'})
        cls.categ_snacks = cls.env['product.category'].create({'name': 'Snacks MCP'})
        cls.wh = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )

        cls.product_with_stock = cls._create_store_product(
            'Agua mineral MCP',
            categ=cls.categ_bebidas,
            with_stock=True,
        )
        cls.product_no_stock = cls._create_store_product(
            'Refresco sin stock MCP',
            categ=cls.categ_bebidas,
            with_stock=False,
        )
        cls.product_not_in_store = cls._create_store_product(
            'Producto oculto MCP',
            visible=False,
            with_stock=True,
        )
        cls.service_product = cls._create_store_product(
            'Servicio MCP consulta',
            product_type='service',
            with_stock=False,
        )
        cls.product_no_category = cls._create_store_product(
            'Snack sin categoria MCP',
            with_stock=True,
        )
        cls.product_snack = cls._create_store_product(
            'Papas fritas MCP',
            categ=cls.categ_snacks,
            with_stock=True,
        )

    @classmethod
    def _create_store_product(
        cls,
        name,
        *,
        categ=None,
        visible=True,
        product_type='consu',
        with_stock=False,
    ):
        vals = {
            'name': name,
            'sale_ok': True,
            'order_bridge_visible': visible,
            'list_price': 1.5,
        }
        if categ:
            vals['categ_id'] = categ.id
        if product_type == 'service':
            vals['type'] = 'service'
        else:
            vals['is_storable'] = True
        tmpl = cls.env['product.template'].create(vals)
        product = tmpl.product_variant_id
        if with_stock and cls.wh and product_type != 'service':
            cls.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': product.id,
                'location_id': cls.wh.lot_stock_id.id,
                'inventory_quantity': 5.0,
            }).action_apply_inventory()
        return product

    def _items(self, result):
        return result['items']

    def _result_ids(self, result):
        return {row['id'] for row in self._items(result)}

    def test_api_search_products_without_query(self):
        result = self.env['product.product'].api_search_products(limit=50)
        ids = self._result_ids(result)
        self.assertIn(self.product_with_stock.id, ids)
        self.assertIn(self.service_product.id, ids)
        self.assertIn(self.product_no_category.id, ids)
        self.assertIn(self.product_snack.id, ids)
        self.assertNotIn(self.product_no_stock.id, ids)
        self.assertNotIn(self.product_not_in_store.id, ids)
        self.assertGreaterEqual(result['total'], 4)

    def test_api_search_products_empty_query(self):
        result = self.env['product.product'].api_search_products(query='   ', limit=50)
        ids = self._result_ids(result)
        self.assertIn(self.product_with_stock.id, ids)
        self.assertNotIn(self.product_no_stock.id, ids)
        self.assertNotIn(self.product_not_in_store.id, ids)

    def test_api_search_products_by_name(self):
        result = self.env['product.product'].api_search_products('Agua mineral')
        items = self._items(result)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], self.product_with_stock.id)
        self.assertEqual(items[0]['category']['name'], 'Bebidas MCP')
        self.assertEqual(result['total'], 1)

    def test_api_search_products_by_category_name(self):
        result = self.env['product.product'].api_search_products('Bebidas MCP')
        ids = self._result_ids(result)
        self.assertIn(self.product_with_stock.id, ids)
        self.assertNotIn(self.product_no_stock.id, ids)

    def test_api_search_products_by_category_id(self):
        result = self.env['product.product'].api_search_products(
            category_id=self.categ_snacks.id,
            limit=50,
        )
        ids = self._result_ids(result)
        self.assertEqual(ids, {self.product_snack.id})
        self.assertEqual(result['total'], 1)

    def test_api_search_products_query_and_category_id(self):
        result = self.env['product.product'].api_search_products(
            query='agua',
            category_id=self.categ_bebidas.id,
            limit=50,
        )
        ids = self._result_ids(result)
        self.assertIn(self.product_with_stock.id, ids)
        self.assertNotIn(self.product_snack.id, ids)

    def test_api_search_products_pagination(self):
        result = self.env['product.product'].api_search_products(limit=2, offset=0)
        self.assertEqual(len(self._items(result)), 2)
        self.assertEqual(result['limit'], 2)
        self.assertEqual(result['offset'], 0)
        self.assertGreaterEqual(result['total'], 4)

        page2 = self.env['product.product'].api_search_products(limit=2, offset=2)
        self.assertEqual(page2['offset'], 2)
        self.assertEqual(page2['total'], result['total'])
        page1_ids = self._result_ids(result)
        page2_ids = self._result_ids(page2)
        self.assertFalse(page1_ids & page2_ids)

    def test_api_search_products_without_category(self):
        result = self.env['product.product'].api_search_products('Snack sin categoria')
        items = self._items(result)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], self.product_no_category.id)
        self.assertFalse(items[0]['category'])

    def test_api_search_products_excludes_storable_without_stock(self):
        result = self.env['product.product'].api_search_products('Refresco sin stock')
        self.assertEqual(self._items(result), [])
        self.assertEqual(result['total'], 0)

    def test_api_search_products_includes_storable_with_stock(self):
        result = self.env['product.product'].api_search_products('Agua mineral MCP')
        items = self._items(result)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], self.product_with_stock.id)

    def test_api_search_products_includes_service_without_quants(self):
        result = self.env['product.product'].api_search_products('Servicio MCP')
        items = self._items(result)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], self.service_product.id)

    def test_api_search_products_invalid_category_id(self):
        with self.assertRaises(Exception):
            self.env['product.product'].api_search_products(category_id=0)

    def test_api_get_product_with_stock(self):
        result = self.env['product.product'].api_get_product(self.product_with_stock.id)
        self.assertEqual(result['id'], self.product_with_stock.id)
        self.assertEqual(result['category']['name'], 'Bebidas MCP')
        self.assertEqual(result['list_price'], 1.5)

    def test_api_get_product_service_without_quants(self):
        result = self.env['product.product'].api_get_product(self.service_product.id)
        self.assertEqual(result['id'], self.service_product.id)

    def test_api_get_product_not_found(self):
        with self.assertRaises(ValidationError) as cm:
            self.env['product.product'].api_get_product(999999999)
        self.assertIn('no está disponible', str(cm.exception))

    def test_api_get_product_not_in_store(self):
        with self.assertRaises(ValidationError) as cm:
            self.env['product.product'].api_get_product(self.product_not_in_store.id)
        self.assertIn('no está disponible', str(cm.exception))

    def test_api_get_product_no_stock(self):
        with self.assertRaises(ValidationError) as cm:
            self.env['product.product'].api_get_product(self.product_no_stock.id)
        self.assertIn('no está disponible', str(cm.exception))


@tagged('post_install', '-at_install')
class TestMcpApiProductProductJson2(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sales_user = cls.env['res.users'].create({
            'name': 'MCP Product JSON2',
            'login': 'mcp_product_json2',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('sales_team.group_sale_salesman').id,
            ])],
        })
        cls.sales_user = cls.sales_user.with_user(cls.sales_user)
        cls.categ = cls.env['product.category'].create({'name': 'JSON2 Bebidas'})
        cls.wh = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1,
        )
        tmpl = cls.env['product.template'].create({
            'name': 'JSON2 Agua MCP',
            'sale_ok': True,
            'order_bridge_visible': True,
            'is_storable': True,
            'list_price': 2.0,
            'categ_id': cls.categ.id,
        })
        cls.product = tmpl.product_variant_id
        if cls.wh:
            cls.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': cls.product.id,
                'location_id': cls.wh.lot_stock_id.id,
                'inventory_quantity': 3.0,
            }).action_apply_inventory()
        key = cls.sales_user.env['res.users.apikeys']._generate(
            scope='rpc',
            name='mcp_product_test',
            expiration_date=datetime.now() + timedelta(days=1),
        )
        cls.bearer_header = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json; charset=utf-8',
        }

    def test_json2_api_search_products_with_query(self):
        payload = {'query': 'JSON2 Bebidas', 'limit': 5}
        res = self.url_open(
            '/json/2/product.product/api_search_products',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(len(body['items']), 1)
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['limit'], 5)
        self.assertEqual(body['offset'], 0)
        self.assertEqual(body['items'][0]['id'], self.product.id)
        self.assertEqual(body['items'][0]['category']['name'], 'JSON2 Bebidas')
        self.assertEqual(body['items'][0]['list_price'], 2.0)

    def test_json2_api_search_products_with_category_id_and_offset(self):
        payload = {
            'category_id': self.categ.id,
            'limit': 10,
            'offset': 0,
        }
        res = self.url_open(
            '/json/2/product.product/api_search_products',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        ids = {row['id'] for row in body['items']}
        self.assertIn(self.product.id, ids)
        self.assertEqual(body['total'], 1)

    def test_json2_api_search_products_without_query(self):
        payload = {'limit': 50}
        res = self.url_open(
            '/json/2/product.product/api_search_products',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        ids = {row['id'] for row in body['items']}
        self.assertIn(self.product.id, ids)
        self.assertIn('total', body)

    def test_json2_api_get_product(self):
        payload = {'product_id': self.product.id}
        res = self.url_open(
            '/json/2/product.product/api_get_product',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body['id'], self.product.id)
        self.assertEqual(body['category']['name'], 'JSON2 Bebidas')
        self.assertEqual(body['list_price'], 2.0)

    def test_json2_api_get_product_not_available(self):
        tmpl = self.env['product.template'].create({
            'name': 'JSON2 Oculto MCP',
            'sale_ok': True,
            'order_bridge_visible': False,
            'is_storable': True,
            'list_price': 1.0,
        })
        payload = {'product_id': tmpl.product_variant_id.id}
        res = self.url_open(
            '/json/2/product.product/api_get_product',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 422, res.text)
