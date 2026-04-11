# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeApi(HttpCase):
    def test_register_and_status_flow(self):
        key = str(uuid.uuid4())
        payload = json.dumps({
            'phone': '+34600111222',
            'device_key': key,
        })
        res = self.url_open(
            '/api/order_bridge/register',
            data=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data.get('status'), 'ok')
        self.assertIn('partner_id', data)
        self.assertFalse(data.get('validated'))
        partner = self.env['res.partner'].browse(data['partner_id'])
        self.assertEqual(partner.name, partner.phone)

        res2 = self.url_open(
            '/api/order_bridge/status',
            headers={'Authorization': f'Bearer {key}'},
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        self.assertFalse(json.loads(res2.text).get('validated'))

    def test_profile_put_get_and_patch(self):
        key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '+34600999888', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        auth = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        put_body = json.dumps({
            'name': 'Profile Customer',
            'address': {
                'street': 'Calle Principal 10',
                'neighborhood': 'Col Norte',
                'municipality': 'Municipio X',
                'state': 'Estado Y',
            },
        })
        r_put = self.url_open(
            '/api/order_bridge/profile',
            data=put_body,
            headers=auth,
            timeout=60,
            method='PUT',
        )
        self.assertEqual(r_put.status_code, 200, r_put.text)
        j_put = json.loads(r_put.text)
        self.assertEqual(j_put.get('name'), 'Profile Customer')
        addr = j_put.get('address') or {}
        self.assertEqual(addr.get('street'), 'Calle Principal 10')

        r_patch = self.url_open(
            '/api/order_bridge/profile',
            data=json.dumps({'address': {'neighborhood': 'Col Sur'}}),
            headers=auth,
            timeout=60,
            method='PATCH',
        )
        self.assertEqual(r_patch.status_code, 200, r_patch.text)
        j_patch = json.loads(r_patch.text)
        self.assertEqual((j_patch.get('address') or {}).get('neighborhood'), 'Col Sur')
        self.assertEqual((j_patch.get('address') or {}).get('street'), 'Calle Principal 10')

    def test_products_public_without_device_key(self):
        self.env['product.template'].create({
            'name': 'Order bridge catalog product',
            'sale_ok': True,
            'order_bridge_visible': True,
            'list_price': 1.0,
        })
        res = self.url_open('/api/order_bridge/products', timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertIn('items', data)
        self.assertNotIn('pos_config_id', data)
        self.assertGreaterEqual(data.get('total', 0), 1)

    def test_register_missing_device_key_returns_400(self):
        res = self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '+34600111200'}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 400, res.text)
        body = json.loads(res.text)
        self.assertEqual(body.get('error'), 'validation')
        self.assertIn('details', body)

    def test_orders_post_requires_device_auth(self):
        res = self.url_open(
            '/api/order_bridge/orders',
            data=json.dumps({'lines': [{'product_id': 1, 'qty': 1}]}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
            method='POST',
        )
        self.assertEqual(res.status_code, 401, res.text)

    def test_products_invalid_category_id_returns_400(self):
        key = str(uuid.uuid4())
        reg = self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '+34600111333', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.assertEqual(reg.status_code, 200, reg.text)
        res = self.url_open(
            '/api/order_bridge/products?category_id=not_int',
            headers={'Authorization': f'Bearer {key}'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 400, res.text)
        data = json.loads(res.text)
        self.assertEqual(data.get('error'), 'validation')
        self.assertIn('details', data)
