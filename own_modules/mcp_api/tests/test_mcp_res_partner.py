# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase


@tagged('post_install', '-at_install')
class TestMcpApiResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.municipality = cls.env['order_bridge.municipality'].create({'name': 'Camaguey MCP'})
        cls.neighborhood = cls.env['order_bridge.neighborhood'].create({
            'name': 'Centro MCP',
            'municipality_id': cls.municipality.id,
        })
        cls.apk_partner = cls.env['res.partner'].create({
            'name': 'Maria MCP Cliente',
            'phone': '+34600111222',
            'email': 'maria@example.com',
        })
        cls.env['order_bridge.partner_address'].create({
            'partner_id': cls.apk_partner.id,
            'street': 'Calle Principal 42',
            'municipality_id': cls.municipality.id,
            'neighborhood_id': cls.neighborhood.id,
            'state': 'Camaguey',
        })
        cls.env['order_bridge.device'].create({
            'device_key': 'mcp-api-search-test',
            'partner_id': cls.apk_partner.id,
            'phone': cls.apk_partner.phone,
            'active': True,
        })
        cls.other_partner = cls.env['res.partner'].create({
            'name': 'Maria Proveedor',
            'phone': '+34600111222',
            'customer_rank': 1,
        })
        cls.apk_no_address = cls.env['res.partner'].create({
            'name': 'Sin Direccion MCP',
            'phone': '+34600999888',
        })
        cls.env['order_bridge.device'].create({
            'device_key': 'mcp-api-no-address',
            'partner_id': cls.apk_no_address.id,
            'phone': cls.apk_no_address.phone,
            'active': True,
        })

    def test_api_search_customers_without_query(self):
        results = self.env['res.partner'].api_search_customers(limit=20)
        ids = {row['id'] for row in results}
        self.assertIn(self.apk_partner.id, ids)
        self.assertIn(self.apk_no_address.id, ids)
        self.assertNotIn(self.other_partner.id, ids)

    def test_api_search_customers_empty_query(self):
        results = self.env['res.partner'].api_search_customers(query='   ', limit=20)
        ids = {row['id'] for row in results}
        self.assertIn(self.apk_partner.id, ids)
        self.assertNotIn(self.other_partner.id, ids)

    def test_api_search_customers_by_name(self):
        results = self.env['res.partner'].api_search_customers('Maria MCP')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.apk_partner.id)
        self.assertTrue(results[0]['address'])
        self.assertEqual(results[0]['address']['street'], 'Calle Principal 42')
        self.assertEqual(results[0]['address']['municipality_name'], 'Camaguey MCP')

    def test_api_search_customers_by_phone(self):
        results = self.env['res.partner'].api_search_customers('600111')
        ids = {row['id'] for row in results}
        self.assertIn(self.apk_partner.id, ids)
        self.assertNotIn(self.other_partner.id, ids)

    def test_api_search_customers_by_street(self):
        results = self.env['res.partner'].api_search_customers('Principal 42')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.apk_partner.id)

    def test_api_search_customers_by_municipality(self):
        results = self.env['res.partner'].api_search_customers('Camaguey MCP')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.apk_partner.id)

    def test_api_search_customers_by_neighborhood(self):
        results = self.env['res.partner'].api_search_customers('Centro MCP')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.apk_partner.id)

    def test_api_search_customers_without_address(self):
        results = self.env['res.partner'].api_search_customers('Sin Direccion')
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]['address'])


@tagged('post_install', '-at_install')
class TestMcpApiResPartnerJson2(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sales_user = cls.env['res.users'].create({
            'name': 'MCP Partner JSON2',
            'login': 'mcp_partner_json2',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('sales_team.group_sale_salesman').id,
            ])],
        })
        cls.sales_user = cls.sales_user.with_user(cls.sales_user)
        cls.municipality = cls.env['order_bridge.municipality'].create({'name': 'JSON2 City'})
        cls.neighborhood = cls.env['order_bridge.neighborhood'].create({
            'name': 'JSON2 Barrio',
            'municipality_id': cls.municipality.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'JSON2 MCP Customer',
            'phone': '+34600777666',
        })
        cls.env['order_bridge.partner_address'].create({
            'partner_id': cls.partner.id,
            'street': 'Avenida JSON2 7',
            'municipality_id': cls.municipality.id,
            'neighborhood_id': cls.neighborhood.id,
            'state': 'JSON2',
        })
        cls.env['order_bridge.device'].create({
            'device_key': 'mcp-json2-partner-search',
            'partner_id': cls.partner.id,
            'phone': cls.partner.phone,
            'active': True,
        })
        key = cls.sales_user.env['res.users.apikeys']._generate(
            scope='rpc',
            name='mcp_partner_test',
            expiration_date=datetime.now() + timedelta(days=1),
        )
        cls.bearer_header = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json; charset=utf-8',
        }

    def test_json2_api_search_customers_with_query(self):
        payload = {'query': 'JSON2 Barrio', 'limit': 5}
        res = self.url_open(
            '/json/2/res.partner/api_search_customers',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['id'], self.partner.id)
        self.assertEqual(body[0]['address']['neighborhood_name'], 'JSON2 Barrio')

    def test_json2_api_search_customers_without_query(self):
        payload = {'limit': 20}
        res = self.url_open(
            '/json/2/res.partner/api_search_customers',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        ids = {row['id'] for row in body}
        self.assertIn(self.partner.id, ids)
