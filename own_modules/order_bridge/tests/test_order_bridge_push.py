# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid
from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgePush(HttpCase):
    def _register(self, key, phone='60011223'):
        return self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': phone, 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )

    @patch('odoo.addons.order_bridge.utils.fcm_client.subscribe_to_topic', return_value=True)
    @patch('odoo.addons.order_bridge.utils.fcm_client.ensure_firebase_app')
    def test_push_token_200(self, _mock_ensure, _mock_sub):
        key = str(uuid.uuid4())
        self.assertEqual(self._register(key).status_code, 200)
        body = json.dumps({
            'fcm_token': 'a' * 140,
            'platform': 'android',
            'subscribe_topics': ['com_culabs_odooshop_all', 'news_topic'],
        })
        res = self.url_open(
            '/api/order_bridge/push/token',
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}',
            },
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('subscribed_topics'), ['com_culabs_odooshop_all', 'news_topic'])

    def test_push_token_401_without_bearer(self):
        res = self.url_open(
            '/api/order_bridge/push/token',
            data=json.dumps({
                'fcm_token': 'x',
                'platform': 'ios',
                'subscribe_topics': [],
            }),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)

    def test_push_token_400_invalid_topic(self):
        key = str(uuid.uuid4())
        self._register(key)
        res = self.url_open(
            '/api/order_bridge/push/token',
            data=json.dumps({
                'fcm_token': 'tok',
                'platform': 'android',
                'subscribe_topics': ['bad topic space'],
            }),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}',
            },
            timeout=60,
        )
        self.assertEqual(res.status_code, 400, res.text)
        self.assertEqual(json.loads(res.text).get('error'), 'validation')

    @patch('odoo.addons.order_bridge.utils.fcm_client.unsubscribe_from_topic', return_value=True)
    @patch('odoo.addons.order_bridge.utils.fcm_client.subscribe_to_topic', return_value=True)
    @patch('odoo.addons.order_bridge.utils.fcm_client.ensure_firebase_app')
    def test_push_token_idempotent(self, _mock_ensure, _mock_sub, _mock_unsub):
        key = str(uuid.uuid4())
        self._register(key)
        auth = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
        }
        b1 = json.dumps({
            'fcm_token': 'first_token_value',
            'platform': 'android',
            'subscribe_topics': ['com_culabs_odooshop_all'],
        })
        r1 = self.url_open('/api/order_bridge/push/token', data=b1, headers=auth, timeout=60)
        self.assertEqual(r1.status_code, 200)
        tok = self.env['order_bridge.push_token'].search([('device_id.device_key', '=', key)])
        self.assertEqual(len(tok), 1)
        self.assertEqual((tok.fcm_token or '').strip(), 'first_token_value')
        b2 = json.dumps({
            'fcm_token': 'rotated_token',
            'platform': 'android',
            'subscribe_topics': ['com_culabs_odooshop_all'],
        })
        r2 = self.url_open('/api/order_bridge/push/token', data=b2, headers=auth, timeout=60)
        self.assertEqual(r2.status_code, 200)
        tok.invalidate_recordset()
        self.assertEqual((tok.fcm_token or '').strip(), 'rotated_token')

    @patch('odoo.addons.order_bridge.utils.fcm_client.unsubscribe_from_topic', return_value=True)
    @patch('odoo.addons.order_bridge.utils.fcm_client.subscribe_to_topic', return_value=True)
    @patch('odoo.addons.order_bridge.utils.fcm_client.ensure_firebase_app')
    def test_push_topics_400_without_prior_token(self, _mock_ensure, _mock_sub, _mock_unsub):
        key = str(uuid.uuid4())
        self._register(key)
        res = self.url_open(
            '/api/order_bridge/push/topics',
            data=json.dumps({
                'subscribe_topics': ['a'],
                'unsubscribe_topics': [],
            }),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}',
            },
            timeout=60,
            method='PATCH',
        )
        self.assertEqual(res.status_code, 400, res.text)
        b = json.loads(res.text)
        self.assertEqual(b.get('error'), 'validation')
        self.assertIn('token', (b.get('message') or '').lower())

    @patch('odoo.addons.order_bridge.utils.fcm_client.unsubscribe_from_topic', return_value=True)
    @patch('odoo.addons.order_bridge.utils.fcm_client.subscribe_to_topic', return_value=True)
    @patch('odoo.addons.order_bridge.utils.fcm_client.ensure_firebase_app')
    def test_push_topics_200(self, _mock_ensure, _mock_sub, _mock_unsub):
        key = str(uuid.uuid4())
        self._register(key)
        auth = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
        }
        self.url_open(
            '/api/order_bridge/push/token',
            data=json.dumps({
                'fcm_token': 't' * 50,
                'platform': 'ios',
                'subscribe_topics': [],
            }),
            headers=auth,
            timeout=60,
        )
        res = self.url_open(
            '/api/order_bridge/push/topics',
            data=json.dumps({
                'subscribe_topics': ['only_good'],
                'unsubscribe_topics': ['com_culabs_odooshop_all'],
            }),
            headers=auth,
            timeout=60,
            method='PATCH',
        )
        self.assertEqual(res.status_code, 200, res.text)
        d = json.loads(res.text)
        self.assertEqual(d.get('status'), 'ok')
        self.assertEqual(d.get('subscribed_topics'), ['only_good'])
