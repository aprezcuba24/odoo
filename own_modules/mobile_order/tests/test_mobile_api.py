# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestMobileOrderApi(HttpCase):
    def test_register_and_status_flow(self):
        key = str(uuid.uuid4())
        payload = json.dumps({
            'phone': '+34600111222',
            'device_key': key,
            'name': 'API Test Customer',
        })
        res = self.url_open(
            '/api/mobile/register',
            data=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data.get('status'), 'ok')
        self.assertIn('partner_id', data)
        self.assertFalse(data.get('validated'))

        res2 = self.url_open(
            '/api/mobile/status',
            headers={'Authorization': f'Bearer {key}'},
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        self.assertFalse(json.loads(res2.text).get('validated'))

    def test_products_requires_auth(self):
        res = self.url_open('/api/mobile/products', timeout=60)
        self.assertEqual(res.status_code, 401)
