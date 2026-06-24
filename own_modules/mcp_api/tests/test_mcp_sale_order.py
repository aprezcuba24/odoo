# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import datetime, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase


@tagged('post_install', '-at_install')
class TestMcpApiSaleOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'MCP Test Customer'})
        cls.product = cls.env['product.product'].create({
            'name': 'MCP Test Product',
            'sale_ok': True,
            'list_price': 10.0,
        })

    def test_api_create_confirmed_order(self):
        result = self.env['sale.order'].api_create_confirmed_order(
            partner_id=self.partner.id,
            lines=[{'product_id': self.product.id, 'qty': 2.0}],
            client_order_ref='MCP-REF-1',
        )
        self.assertEqual(result['state'], 'sale')
        self.assertEqual(result['partner_id'], self.partner.id)
        self.assertEqual(result['client_order_ref'], 'MCP-REF-1')
        order = self.env['sale.order'].browse(result['id'])
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_uom_qty, 2.0)

    def test_api_create_confirmed_order_bridge(self):
        result = self.env['sale.order'].api_create_confirmed_order_bridge(
            partner_id=self.partner.id,
            lines=[{'product_id': self.product.id, 'product_uom_qty': 1.0}],
        )
        order = self.env['sale.order'].browse(result['id'])
        self.assertEqual(order.order_bridge_origin, 'admin')
        self.assertEqual(result['state'], 'sale')

    def test_api_create_confirmed_order_invalid_partner(self):
        with self.assertRaises(ValidationError):
            self.env['sale.order'].api_create_confirmed_order(
                partner_id=999999,
                lines=[{'product_id': self.product.id, 'qty': 1.0}],
            )

    def test_api_create_confirmed_order_respects_acl(self):
        user = self.env['res.users'].create({
            'name': 'MCP Limited User',
            'login': 'mcp_limited_user',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.env['sale.order'].with_user(user).api_create_confirmed_order(
                partner_id=self.partner.id,
                lines=[{'product_id': self.product.id, 'qty': 1.0}],
            )


@tagged('post_install', '-at_install')
class TestMcpApiJson2(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sales_user = cls.env['res.users'].create({
            'name': 'MCP Sales JSON2',
            'login': 'mcp_sales_json2',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('sales_team.group_sale_salesman').id,
            ])],
        })
        cls.sales_user = cls.sales_user.with_user(cls.sales_user)
        cls.partner = cls.env['res.partner'].create({'name': 'MCP JSON2 Customer'})
        cls.product = cls.env['product.product'].create({
            'name': 'MCP JSON2 Product',
            'sale_ok': True,
            'list_price': 5.0,
        })
        key = cls.sales_user.env['res.users.apikeys']._generate(
            scope='rpc',
            name='mcp_api_test',
            expiration_date=datetime.now() + timedelta(days=1),
        )
        cls.bearer_header = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json; charset=utf-8',
        }

    def test_json2_api_create_confirmed_order(self):
        payload = {
            'partner_id': self.partner.id,
            'lines': [{'product_id': self.product.id, 'qty': 3.0}],
            'client_order_ref': 'JSON2-1',
        }
        res = self.url_open(
            '/json/2/sale.order/api_create_confirmed_order',
            data=json.dumps(payload),
            headers=self.bearer_header,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body['state'], 'sale')
        self.assertEqual(body['client_order_ref'], 'JSON2-1')
