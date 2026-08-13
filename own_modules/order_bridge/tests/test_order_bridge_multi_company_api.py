# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""HTTP isolation: catalog/register resolve company via company_slug."""

import json
import uuid

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeMultiCompanyApi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('es_ES')
        # Tag main company so slug-based catalog works without permanently
        # leaving a second active company (HttpCase commits).
        cls.main_company = cls.env.company
        if not cls.main_company.order_bridge_slug:
            cls.main_company.order_bridge_slug = 'main-store'

    def test_anonymous_catalog_requires_slug_when_multi_company(self):
        extra = self.env['res.company'].create({
            'name': 'Temp API Co',
            'order_bridge_slug': 'temp-api-co',
        })
        try:
            res = self.url_open('/api/order_bridge/products', timeout=60)
            self.assertEqual(res.status_code, 400, res.text)
            self.assertEqual(json.loads(res.text).get('error'), 'company_slug_required')
        finally:
            extra.active = False

    def test_anonymous_catalog_filtered_by_slug(self):
        company_b = self.env['res.company'].create({
            'name': 'API Co B Http',
            'order_bridge_slug': 'api-b-http',
        })
        try:
            self.env['product.template'].create({
                'name': 'Prod Main only',
                'sale_ok': True,
                'order_bridge_visible': True,
                'list_price': 5.0,
                'company_id': self.main_company.id,
            })
            self.env['product.template'].create({
                'name': 'Prod B Http only',
                'sale_ok': True,
                'order_bridge_visible': True,
                'list_price': 7.0,
                'company_id': company_b.id,
            })
            res_a = self.url_open(
                '/api/order_bridge/products',
                headers={'X-Company-Slug': self.main_company.order_bridge_slug},
                timeout=60,
            )
            self.assertEqual(res_a.status_code, 200, res_a.text)
            names_a = [i['name'] for i in json.loads(res_a.text).get('items', [])]
            self.assertTrue(any('Prod Main' in n for n in names_a), names_a)
            self.assertFalse(any('Prod B Http' in n for n in names_a), names_a)

            res_b = self.url_open(
                '/api/order_bridge/products?company_slug=api-b-http',
                timeout=60,
            )
            self.assertEqual(res_b.status_code, 200, res_b.text)
            names_b = [i['name'] for i in json.loads(res_b.text).get('items', [])]
            self.assertTrue(any('Prod B Http' in n for n in names_b), names_b)
            self.assertFalse(any('Prod Main' in n for n in names_b), names_b)
        finally:
            company_b.active = False

    def test_register_with_company_slug(self):
        key = str(uuid.uuid4())
        res = self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({
                'phone': '60033344',
                'device_key': key,
                'company_slug': self.main_company.order_bridge_slug,
            }),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        device = self.env['order_bridge.device'].search([('device_key', '=', key)], limit=1)
        self.assertEqual(device.company_id, self.main_company)
        self.assertEqual(device.partner_id.company_id, self.main_company)
