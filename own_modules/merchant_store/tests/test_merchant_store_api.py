# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid

from odoo import Command
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestMerchantStoreApi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('es_ES')
        Company = cls.env['res.company']
        cls.company_a = Company.create({
            'name': 'Merchant API Co A',
            'order_bridge_slug': 'merchant-api-co-a',
        })
        cls.company_b = Company.create({
            'name': 'Merchant API Co B',
            'order_bridge_slug': 'merchant-api-co-b',
        })
        cls._enable_merchant_store_app(cls.company_a)
        cls._enable_merchant_store_app(cls.company_b)

        Merchant = cls.env['merchant_store.merchant']
        cls.merchant_a = Merchant.create({
            'name': 'API Merchant A',
            'company_id': cls.company_a.id,
        })
        cls.merchant_a2 = Merchant.create({
            'name': 'API Merchant A2',
            'company_id': cls.company_a.id,
        })
        cls.merchant_a_archived = Merchant.create({
            'name': 'API Merchant Archived',
            'company_id': cls.company_a.id,
            'active': False,
        })
        cls.merchant_b = Merchant.create({
            'name': 'API Merchant B',
            'company_id': cls.company_b.id,
        })

        ProductTemplate = cls.env['product.template']
        cls.product_a = ProductTemplate.with_company(cls.company_a).create({
            'name': 'API producto A',
            'list_price': 20.0,
            'merchant_id': cls.merchant_a.id,
            'sale_ok': True,
        })
        cls.product_a2 = ProductTemplate.with_company(cls.company_a).create({
            'name': 'API producto A2',
            'list_price': 15.0,
            'merchant_id': cls.merchant_a2.id,
            'sale_ok': True,
        })
        cls.product_archived_merchant = ProductTemplate.with_company(cls.company_a).create({
            'name': 'API producto archivado',
            'list_price': 8.0,
            'merchant_id': cls.merchant_a_archived.id,
            'sale_ok': True,
        })
        cls.product_b = ProductTemplate.with_company(cls.company_b).create({
            'name': 'API producto B',
            'list_price': 12.0,
            'merchant_id': cls.merchant_b.id,
            'sale_ok': True,
        })
        cls.own_product_a = ProductTemplate.with_company(cls.company_a).create({
            'name': 'API producto propio',
            'list_price': 10.0,
            'company_id': cls.company_a.id,
            'sale_ok': True,
            'order_bridge_visible': True,
        })

    @classmethod
    def _enable_merchant_store_app(cls, company):
        optional = cls.env['ir.model.data'].sudo().search([
            ('module', '=', 'company_onboarding'),
            ('name', '=', 'optional_app_merchant_store'),
        ], limit=1)
        if not optional:
            return
        app = cls.env['company.optional.app'].browse(optional.res_id)
        if app.exists() and app not in company.optional_app_ids:
            company.write({'optional_app_ids': [Command.link(app.id)]})

    def _register_device(self, company, phone=None):
        key = str(uuid.uuid4())
        phone = phone or f'6{uuid.uuid4().int % 10_000_000:07d}'
        payload = {
            'phone': phone,
            'device_key': key,
            'company_slug': company.order_bridge_slug,
        }
        res = self.url_open(
            '/api/order_bridge/register',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        device = self.env['order_bridge.device'].search([('device_key', '=', key)], limit=1)
        self.assertTrue(device)
        self.assertEqual(device.company_id, company)
        return key, device

    def _auth_headers(self, key, content_type=False):
        headers = {'Authorization': f'Bearer {key}'}
        if content_type:
            headers['Content-Type'] = 'application/json'
        return headers

    def test_merchants_requires_bearer(self):
        res = self.url_open('/api/merchant_store/merchants', timeout=60)
        self.assertEqual(res.status_code, 401, res.text)

    def test_merchants_company_isolation_and_active_only(self):
        key_a, _device_a = self._register_device(self.company_a)
        key_b, _device_b = self._register_device(self.company_b)

        res_a = self.url_open(
            '/api/merchant_store/merchants',
            headers=self._auth_headers(key_a),
            timeout=60,
        )
        self.assertEqual(res_a.status_code, 200, res_a.text)
        data_a = json.loads(res_a.text)
        names_a = {item['name'] for item in data_a['items']}
        self.assertIn('API Merchant A', names_a)
        self.assertIn('API Merchant A2', names_a)
        self.assertNotIn('API Merchant Archived', names_a)
        self.assertNotIn('API Merchant B', names_a)

        res_b = self.url_open(
            '/api/merchant_store/merchants',
            headers=self._auth_headers(key_b),
            timeout=60,
        )
        self.assertEqual(res_b.status_code, 200, res_b.text)
        names_b = {item['name'] for item in json.loads(res_b.text)['items']}
        self.assertEqual(names_b, {'API Merchant B'})

    def test_products_exclude_archived_merchant_and_other_company(self):
        key_a, _device = self._register_device(self.company_a)
        res = self.url_open(
            '/api/merchant_store/products',
            headers=self._auth_headers(key_a),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        items = json.loads(res.text)['items']
        ids = {item['id'] for item in items}
        self.assertIn(self.product_a.product_variant_id.id, ids)
        self.assertIn(self.product_a2.product_variant_id.id, ids)
        self.assertNotIn(self.product_archived_merchant.product_variant_id.id, ids)
        self.assertNotIn(self.product_b.product_variant_id.id, ids)
        self.assertNotIn(self.own_product_a.product_variant_id.id, ids)

        res_detail = self.url_open(
            f'/api/merchant_store/products/{self.product_archived_merchant.product_variant_id.id}',
            headers=self._auth_headers(key_a),
            timeout=60,
        )
        self.assertEqual(res_detail.status_code, 404, res_detail.text)

    def test_checkout_splits_idempotent_and_rejects_bad_lines(self):
        key_a, device_a = self._register_device(self.company_a)
        auth = self._auth_headers(key_a, content_type=True)
        payload = {
            'client_checkout_id': str(uuid.uuid4()),
            'lines': [
                {'product_id': self.product_a.product_variant_id.id, 'qty': 2},
                {'product_id': self.product_a2.product_variant_id.id, 'qty': 1},
            ],
        }
        res = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps(payload),
            headers=auth,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data['client_checkout_id'], payload['client_checkout_id'])
        self.assertEqual(len(data['orders']), 2)
        for order in data['orders']:
            self.assertEqual(order['store_state'], 'reviewing')
            self.assertEqual(order['state'], 'draft')
            self.assertTrue(order['merchant_id'])

        res2 = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                **payload,
                'lines': [
                    {'product_id': self.product_a.product_variant_id.id, 'qty': 99},
                ],
            }),
            headers=auth,
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        data2 = json.loads(res2.text)
        self.assertEqual(
            {o['id'] for o in data['orders']},
            {o['id'] for o in data2['orders']},
        )

        bad_own = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': str(uuid.uuid4()),
                'lines': [
                    {'product_id': self.own_product_a.product_variant_id.id, 'qty': 1},
                ],
            }),
            headers=auth,
            timeout=60,
        )
        self.assertEqual(bad_own.status_code, 400, bad_own.text)

        bad_other = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': str(uuid.uuid4()),
                'lines': [
                    {'product_id': self.product_b.product_variant_id.id, 'qty': 1},
                ],
            }),
            headers=auth,
            timeout=60,
        )
        self.assertEqual(bad_other.status_code, 400, bad_other.text)

        bad_archived = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': str(uuid.uuid4()),
                'lines': [
                    {
                        'product_id': self.product_archived_merchant.product_variant_id.id,
                        'qty': 1,
                    },
                ],
            }),
            headers=auth,
            timeout=60,
        )
        self.assertEqual(bad_archived.status_code, 400, bad_archived.text)

        key_b, _device_b = self._register_device(self.company_b)
        stolen = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps(payload),
            headers=self._auth_headers(key_b, content_type=True),
            timeout=60,
        )
        # Same checkout id in another company is a different unique key; must not see A's lines.
        # Buying A's products from B fails with 400.
        self.assertEqual(stolen.status_code, 400, stolen.text)
        self.assertTrue(device_a)

    def test_orders_detail_and_archived_merchant_still_listed(self):
        key_a, device_a = self._register_device(self.company_a)
        auth = self._auth_headers(key_a, content_type=True)
        checkout_id = str(uuid.uuid4())
        res = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': checkout_id,
                'lines': [
                    {'product_id': self.product_a.product_variant_id.id, 'qty': 1},
                ],
            }),
            headers=auth,
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        order_id = json.loads(res.text)['orders'][0]['id']

        self.merchant_a.active = False

        list_res = self.url_open(
            '/api/merchant_store/orders',
            headers=self._auth_headers(key_a),
            timeout=60,
        )
        self.assertEqual(list_res.status_code, 200, list_res.text)
        ids = {item['id'] for item in json.loads(list_res.text)['items']}
        self.assertIn(order_id, ids)

        detail = self.url_open(
            f'/api/merchant_store/orders/{order_id}',
            headers=self._auth_headers(key_a),
            timeout=60,
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        body = json.loads(detail.text)
        self.assertEqual(body['store_state'], 'reviewing')
        self.assertEqual(body['merchant_id'], self.merchant_a.id)

        key_other, _ = self._register_device(self.company_a, phone='60999888')
        foreign = self.url_open(
            f'/api/merchant_store/orders/{order_id}',
            headers=self._auth_headers(key_other),
            timeout=60,
        )
        self.assertEqual(foreign.status_code, 404, foreign.text)

        apk = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': device_a.partner_id.id,
            'company_id': self.company_a.id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })
        no_merchant = self.url_open(
            f'/api/merchant_store/orders/{apk.id}',
            headers=self._auth_headers(key_a),
            timeout=60,
        )
        self.assertEqual(no_merchant.status_code, 404, no_merchant.text)

    def test_optional_app_disabled_returns_404(self):
        optional = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'company_onboarding'),
            ('name', '=', 'optional_app_merchant_store'),
        ], limit=1)
        if not optional:
            self.skipTest('company_onboarding not installed')
        app = self.env['company.optional.app'].browse(optional.res_id)
        company = self.env['res.company'].create({
            'name': 'Merchant API Co Off',
            'order_bridge_slug': 'merchant-api-co-off',
        })
        if app in company.optional_app_ids:
            company.write({'optional_app_ids': [Command.unlink(app.id)]})
        self.assertFalse(company.has_optional_app('merchant_store'))

        key, _device = self._register_device(company)
        res = self.url_open(
            '/api/merchant_store/merchants',
            headers=self._auth_headers(key),
            timeout=60,
        )
        self.assertEqual(res.status_code, 404, res.text)
