# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid

from odoo import Command
from odoo.tests.common import HttpCase, tagged

from odoo.addons.order_bridge.schemas.responses import (
    OrderCreatedResponse,
    SaleOrderDetailResponse,
    SaleOrderSummary,
)


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

    def test_merchant_detail_own_archived_and_other_company(self):
        key_a, _device_a = self._register_device(self.company_a)
        headers_a = self._auth_headers(key_a)

        res_ok = self.url_open(
            f'/api/merchant_store/merchants/{self.merchant_a.id}',
            headers=headers_a,
            timeout=60,
        )
        self.assertEqual(res_ok.status_code, 200, res_ok.text)
        payload = json.loads(res_ok.text)
        self.assertEqual(payload['id'], self.merchant_a.id)
        self.assertEqual(payload['name'], 'API Merchant A')

        res_archived = self.url_open(
            f'/api/merchant_store/merchants/{self.merchant_a_archived.id}',
            headers=headers_a,
            timeout=60,
        )
        self.assertEqual(res_archived.status_code, 404, res_archived.text)

        res_other = self.url_open(
            f'/api/merchant_store/merchants/{self.merchant_b.id}',
            headers=headers_a,
            timeout=60,
        )
        self.assertEqual(res_other.status_code, 404, res_other.text)

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
        self.assertEqual(body['merchant_name'], self.merchant_a.name)

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

    def test_purchases_grouping_mixed_merchant_only_store_only_and_isolation(self):
        key_a, device_a = self._register_device(self.company_a)
        auth_json = self._auth_headers(key_a, content_type=True)
        auth = self._auth_headers(key_a)

        # 1) Compra solo tienda (sin subórdenes)
        store_only = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': device_a.partner_id.id,
            'company_id': self.company_a.id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })

        # 2) Compra mixta: pedido propio + subórdenes de dos comercios
        mixed_own = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': device_a.partner_id.id,
            'company_id': self.company_a.id,
            'order_bridge_origin': 'app',
            'order_line': [Command.create({
                'product_id': self.own_product_a.product_variant_id.id,
                'product_uom_qty': 1.0,
            })],
        })
        mixed_checkout_id = str(uuid.uuid4())
        mixed_res = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': mixed_checkout_id,
                'order_bridge_order_id': mixed_own.id,
                'lines': [
                    {'product_id': self.product_a.product_variant_id.id, 'qty': 1},
                    {'product_id': self.product_a2.product_variant_id.id, 'qty': 2},
                ],
            }),
            headers=auth_json,
            timeout=60,
        )
        self.assertEqual(mixed_res.status_code, 200, mixed_res.text)
        mixed_subs = json.loads(mixed_res.text)['orders']
        self.assertEqual(
            {s['merchant_name'] for s in mixed_subs},
            {self.merchant_a.name, self.merchant_a2.name},
        )

        # 3) Compra solo comercio (sin pedido propio)
        merchant_only_checkout_id = str(uuid.uuid4())
        only_m_res = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': merchant_only_checkout_id,
                'lines': [
                    {'product_id': self.product_a.product_variant_id.id, 'qty': 1},
                ],
            }),
            headers=auth_json,
            timeout=60,
        )
        self.assertEqual(only_m_res.status_code, 200, only_m_res.text)

        purchases_res = self.url_open(
            '/api/merchant_store/purchases',
            headers=auth,
            timeout=60,
        )
        self.assertEqual(purchases_res.status_code, 200, purchases_res.text)
        data = json.loads(purchases_res.text)
        self.assertEqual(data['total'], 3)
        by_key = {row['purchase_key']: row for row in data['items']}

        # Fila mixta
        mixed_row = by_key[f'order:{mixed_own.id}']
        self.assertEqual(mixed_row['client_checkout_id'], mixed_checkout_id)
        self.assertEqual(mixed_row['order']['id'], mixed_own.id)
        self.assertEqual(len(mixed_row['suborders']), 2)
        self.assertEqual(
            {s['merchant_name'] for s in mixed_row['suborders']},
            {self.merchant_a.name, self.merchant_a2.name},
        )
        expected_mixed_total = float(mixed_own.amount_total) + sum(
            float(s['amount_total']) for s in mixed_row['suborders']
        )
        self.assertAlmostEqual(mixed_row['amount_total'], expected_mixed_total, places=2)

        # Fila solo comercio
        only_m_row = by_key[f'checkout:{merchant_only_checkout_id}']
        self.assertIsNone(only_m_row['order'])
        self.assertEqual(only_m_row['client_checkout_id'], merchant_only_checkout_id)
        self.assertEqual(len(only_m_row['suborders']), 1)
        self.assertEqual(only_m_row['suborders'][0]['merchant_name'], self.merchant_a.name)
        self.assertAlmostEqual(
            only_m_row['amount_total'],
            only_m_row['suborders'][0]['amount_total'],
            places=2,
        )

        # Fila solo tienda
        store_row = by_key[f'order:{store_only.id}']
        self.assertIsNone(store_row['client_checkout_id'])
        self.assertEqual(store_row['order']['id'], store_only.id)
        self.assertEqual(store_row['suborders'], [])
        self.assertAlmostEqual(store_row['amount_total'], float(store_only.amount_total), places=2)

        # Otro partner de la misma compañía no ve estas compras
        key_other, _ = self._register_device(self.company_a, phone='60777666')
        other_res = self.url_open(
            '/api/merchant_store/purchases',
            headers=self._auth_headers(key_other),
            timeout=60,
        )
        self.assertEqual(other_res.status_code, 200, other_res.text)
        self.assertEqual(json.loads(other_res.text)['total'], 0)

    def test_legacy_order_bridge_api_flow_with_merchant_store_installed(self):
        """Legacy mobile apps using /api/order_bridge/* keep working with merchant_store."""
        key_a, _device_a = self._register_device(self.company_a)
        auth = self._auth_headers(key_a)
        auth_json = self._auth_headers(key_a, content_type=True)
        own_variant_id = self.own_product_a.product_variant_id.id
        merchant_variant_id = self.product_a.product_variant_id.id

        # 1) Legacy catalog includes own product and excludes merchant product.
        catalog_res = self.url_open(
            '/api/order_bridge/products',
            headers=auth,
            timeout=60,
        )
        self.assertEqual(catalog_res.status_code, 200, catalog_res.text)
        catalog_ids = {item['id'] for item in json.loads(catalog_res.text)['items']}
        self.assertIn(own_variant_id, catalog_ids)
        self.assertNotIn(merchant_variant_id, catalog_ids)

        # 2) Legacy POST /api/order_bridge/orders creates own order and is idempotent.
        client_order_id_1 = str(uuid.uuid4())
        payload_1 = json.dumps({
            'client_order_id': client_order_id_1,
            'lines': [{'product_id': own_variant_id, 'qty': 1}],
        })
        create_res_1 = self.url_open(
            '/api/order_bridge/orders',
            data=payload_1,
            headers=auth_json,
            method='POST',
            timeout=60,
        )
        self.assertEqual(create_res_1.status_code, 200, create_res_1.text)
        created_1 = json.loads(create_res_1.text)
        self.assertEqual(set(created_1.keys()), set(OrderCreatedResponse.model_fields.keys()))
        self.assertFalse(any(k.startswith('merchant_') for k in created_1))

        order_1 = self.env['sale.order'].sudo().browse(created_1['id'])
        self.assertEqual(order_1.order_bridge_origin, 'app')
        self.assertFalse(order_1.merchant_id)

        retry_res_1 = self.url_open(
            '/api/order_bridge/orders',
            data=payload_1,
            headers=auth_json,
            method='POST',
            timeout=60,
        )
        self.assertEqual(retry_res_1.status_code, 200, retry_res_1.text)
        self.assertEqual(json.loads(retry_res_1.text)['id'], created_1['id'])

        # 3) Second legacy POST with another client_order_id succeeds (NULL uniqueness).
        create_res_2 = self.url_open(
            '/api/order_bridge/orders',
            data=json.dumps({
                'client_order_id': str(uuid.uuid4()),
                'lines': [{'product_id': own_variant_id, 'qty': 1}],
            }),
            headers=auth_json,
            method='POST',
            timeout=60,
        )
        self.assertEqual(create_res_2.status_code, 200, create_res_2.text)
        created_2 = json.loads(create_res_2.text)
        self.assertNotEqual(created_2['id'], created_1['id'])

        # 4) Legacy POST rejects merchant products with 400.
        bad_res = self.url_open(
            '/api/order_bridge/orders',
            data=json.dumps({
                'client_order_id': str(uuid.uuid4()),
                'lines': [{'product_id': merchant_variant_id, 'qty': 1}],
            }),
            headers=auth_json,
            method='POST',
            timeout=60,
        )
        self.assertEqual(bad_res.status_code, 400, bad_res.text)

        # 5) Merchant checkouts (one linked to order 1, one merchant-only).
        linked_checkout_res = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': str(uuid.uuid4()),
                'order_bridge_order_id': created_1['id'],
                'lines': [{'product_id': merchant_variant_id, 'qty': 1}],
            }),
            headers=auth_json,
            timeout=60,
        )
        self.assertEqual(linked_checkout_res.status_code, 200, linked_checkout_res.text)
        suborder_id = json.loads(linked_checkout_res.text)['orders'][0]['id']

        only_merchant_res = self.url_open(
            '/api/merchant_store/checkouts',
            data=json.dumps({
                'client_checkout_id': str(uuid.uuid4()),
                'lines': [{'product_id': merchant_variant_id, 'qty': 2}],
            }),
            headers=auth_json,
            timeout=60,
        )
        self.assertEqual(only_merchant_res.status_code, 200, only_merchant_res.text)

        # 6) Legacy GET /api/order_bridge/orders lists only the two own orders.
        list_res = self.url_open(
            '/api/order_bridge/orders',
            headers=auth,
            timeout=60,
        )
        self.assertEqual(list_res.status_code, 200, list_res.text)
        list_data = json.loads(list_res.text)
        self.assertEqual(list_data['total'], 2)
        items_by_id = {item['id']: item for item in list_data['items']}
        self.assertEqual(set(items_by_id.keys()), {created_1['id'], created_2['id']})
        for item in list_data['items']:
            self.assertEqual(set(item.keys()), set(SaleOrderSummary.model_fields.keys()))
        self.assertAlmostEqual(
            items_by_id[created_1['id']]['amount_total'],
            created_1['amount_total'],
            places=2,
        )
        self.assertEqual(
            items_by_id[created_1['id']]['store_state'],
            created_1['store_state'],
        )

        # 7) Legacy GET detail works for own order and returns 404 for a suborder.
        detail_res = self.url_open(
            f"/api/order_bridge/orders/{created_1['id']}",
            headers=auth,
            timeout=60,
        )
        self.assertEqual(detail_res.status_code, 200, detail_res.text)
        detail = json.loads(detail_res.text)
        self.assertEqual(set(detail.keys()), set(SaleOrderDetailResponse.model_fields.keys()))
        self.assertEqual(len(detail['lines']), 1)
        self.assertEqual(detail['lines'][0]['product_id'], own_variant_id)

        sub_detail_res = self.url_open(
            f'/api/order_bridge/orders/{suborder_id}',
            headers=auth,
            timeout=60,
        )
        self.assertEqual(sub_detail_res.status_code, 404, sub_detail_res.text)
