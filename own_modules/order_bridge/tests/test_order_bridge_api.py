# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import uuid
from urllib.parse import urlparse

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeApi(HttpCase):
    def test_register_and_status_flow(self):
        key = str(uuid.uuid4())
        payload = json.dumps({
            'phone': '60011122',
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
            data=json.dumps({'phone': '60099988', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        m = self.env['order_bridge.municipality'].create({'name': 'Municipio X'})
        n1 = self.env['order_bridge.neighborhood'].create({
            'name': 'Col Norte',
            'municipality_id': m.id,
        })
        n2 = self.env['order_bridge.neighborhood'].create({
            'name': 'Col Sur',
            'municipality_id': m.id,
        })
        auth = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        put_body = json.dumps({
            'name': 'Profile Customer',
            'address': {
                'street': 'Calle Principal 10',
                'municipality_id': m.id,
                'neighborhood_id': n1.id,
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
        self.assertEqual(addr.get('municipality_id'), m.id)
        self.assertEqual(addr.get('neighborhood_id'), n1.id)

        r_patch = self.url_open(
            '/api/order_bridge/profile',
            data=json.dumps({'address': {'neighborhood_id': n2.id, 'municipality_id': m.id}}),
            headers=auth,
            timeout=60,
            method='PATCH',
        )
        self.assertEqual(r_patch.status_code, 200, r_patch.text)
        j_patch = json.loads(r_patch.text)
        self.assertEqual((j_patch.get('address') or {}).get('neighborhood_id'), n2.id)
        self.assertEqual((j_patch.get('address') or {}).get('street'), 'Calle Principal 10')

    def test_profile_patch_address_street_without_municipality_neighborhood_returns_400(self):
        key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60077766', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        m = self.env['order_bridge.municipality'].create({'name': 'Mun Patch'})
        self.env['order_bridge.neighborhood'].create({
            'name': 'Bar Patch',
            'municipality_id': m.id,
        })
        auth = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        res = self.url_open(
            '/api/order_bridge/profile',
            data=json.dumps({'address': {'street': 'Solo calle sin ubicación'}}),
            headers=auth,
            timeout=60,
            method='PATCH',
        )
        self.assertEqual(res.status_code, 400, res.text)
        body = json.loads(res.text)
        self.assertEqual(body.get('error'), 'validation')
        self.assertIn('municipio', (body.get('message') or '').lower())
        self.assertIn('barrio', (body.get('message') or '').lower())

    def test_municipalities_public_list(self):
        m = self.env['order_bridge.municipality'].create({'name': 'Mun API'})
        self.env['order_bridge.neighborhood'].create({
            'name': 'Bar 1',
            'municipality_id': m.id,
        })
        res = self.url_open('/api/order_bridge/municipalities', timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertIn('items', data)
        self.assertGreaterEqual(data.get('total', 0), 1)
        row = next((x for x in data['items'] if x['id'] == m.id), None)
        self.assertTrue(row)
        self.assertEqual(len(row['neighborhoods']), 1)
        self.assertEqual(row['neighborhoods'][0]['name'], 'Bar 1')

    def test_products_public_without_device_key(self):
        self.env['product.template'].create({
            'name': 'Producto catálogo Tienda Apk',
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

    def test_settings_get_shop_phone(self):
        company = self.env.company.sudo()
        rec = self.env['order_bridge.general_settings'].sudo()._get_or_create_for_company(company)
        rec.write({'shop_phone': '+34 900 111 222'})
        res = self.url_open('/api/order_bridge/settings', timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data.get('shop_phone'), '+34 900 111 222')

    def test_register_missing_device_key_returns_400(self):
        res = self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011120'}),
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

    def test_orders_post_storable_insufficient_stock_returns_400_after_first_confirmed(self):
        key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011224', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        tmpl = self.env['product.template'].create({
            'name': 'Storable OB stock test',
            'sale_ok': True,
            'order_bridge_visible': True,
            'is_storable': True,
            'list_price': 10.0,
        })
        product = tmpl.product_variant_id
        wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        self.assertTrue(wh)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': wh.lot_stock_id.id,
            'inventory_quantity': 1.0,
        }).action_apply_inventory()

        auth = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        ok = self.url_open(
            '/api/order_bridge/orders',
            data=json.dumps({'lines': [{'product_id': product.id, 'qty': 1}]}),
            headers=auth,
            method='POST',
            timeout=60,
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        created = json.loads(ok.text)
        self.assertEqual(created.get('state'), 'sale')
        self.assertIn('delivery_status', created)
        self.assertIn('effective_date', created)
        self.assertEqual(created.get('delivery_status'), 'pending')
        self.assertIsNone(created.get('effective_date'))

        bad = self.url_open(
            '/api/order_bridge/orders',
            data=json.dumps({'lines': [{'product_id': product.id, 'qty': 1}]}),
            headers=auth,
            method='POST',
            timeout=60,
        )
        self.assertEqual(bad.status_code, 400, bad.text)
        payload = json.loads(bad.text)
        self.assertEqual(payload.get('error'), 'insufficient_stock')
        products = payload.get('products')
        self.assertIsInstance(products, list)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].get('product_id'), product.id)
        self.assertEqual(products[0].get('available_qty'), 0.0)

    def test_orders_get_list_includes_delivery_fields(self):
        key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011225', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        tmpl = self.env['product.template'].create({
            'name': 'Storable OB delivery list test',
            'sale_ok': True,
            'order_bridge_visible': True,
            'is_storable': True,
            'list_price': 10.0,
        })
        product = tmpl.product_variant_id
        wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        self.assertTrue(wh)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': wh.lot_stock_id.id,
            'inventory_quantity': 5.0,
        }).action_apply_inventory()

        auth = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        post = self.url_open(
            '/api/order_bridge/orders',
            data=json.dumps({'lines': [{'product_id': product.id, 'qty': 1}]}),
            headers=auth,
            method='POST',
            timeout=60,
        )
        self.assertEqual(post.status_code, 200, post.text)

        res = self.url_open(
            '/api/order_bridge/orders',
            headers={'Authorization': f'Bearer {key}'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        items = data.get('items') or []
        self.assertTrue(items)
        row = items[0]
        self.assertIn('delivery_status', row)
        self.assertIn('effective_date', row)
        self.assertEqual(row.get('delivery_status'), 'pending')

    def test_order_detail_includes_line_product_images(self):
        png_b64 = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        )
        tmpl = self.env['product.template'].create({
            'name': 'Servicio imagen detalle pedido',
            'sale_ok': True,
            'order_bridge_visible': True,
            'list_price': 3.0,
            'type': 'service',
            'image_1920': png_b64,
        })
        product = tmpl.product_variant_id
        key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011555', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        auth = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        post = self.url_open(
            '/api/order_bridge/orders',
            data=json.dumps({'lines': [{'product_id': product.id, 'qty': 1}]}),
            headers=auth,
            method='POST',
            timeout=60,
        )
        self.assertEqual(post.status_code, 200, post.text)
        order_id = json.loads(post.text)['id']
        res = self.url_open(
            f'/api/order_bridge/orders/{order_id}',
            headers={'Authorization': f'Bearer {key}'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        detail = json.loads(res.text)
        lines = detail.get('lines') or []
        self.assertTrue(lines)
        self.assertIn(f'/web/image/product.product/{product.id}/image_512', lines[0].get('image_url') or '')

    def test_products_list_includes_image_urls_and_public_image_loads(self):
        png_b64 = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        )
        tmpl = self.env['product.template'].create({
            'name': 'Producto con imagen OB',
            'sale_ok': True,
            'order_bridge_visible': True,
            'list_price': 1.0,
            'image_1920': png_b64,
        })
        product = tmpl.product_variant_id
        key = str(uuid.uuid4())
        self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011444', 'device_key': key}),
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        res = self.url_open(
            '/api/order_bridge/products',
            headers={'Authorization': f'Bearer {key}'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        row = next((x for x in data['items'] if x['id'] == product.id), None)
        self.assertTrue(row)
        self.assertTrue(row.get('image_url'))
        self.assertTrue(row.get('image_thumbnail_url'))
        self.assertIn(f'/web/image/product.product/{product.id}/image_512', row['image_url'])
        self.assertIn(f'/web/image/product.product/{product.id}/image_128', row['image_thumbnail_url'])
        parsed = urlparse(row['image_url'])
        path = parsed.path
        if parsed.query:
            path = f'{path}?{parsed.query}'
        img_res = self.url_open(path, timeout=60)
        self.assertEqual(img_res.status_code, 200, img_res.text)
        self.assertIn('image', (img_res.headers.get('Content-Type') or '').lower())

    def test_banners_list_empty_and_with_image_loads(self):
        res_empty = self.url_open('/api/order_bridge/banners', timeout=60)
        self.assertEqual(res_empty.status_code, 200, res_empty.text)
        empty = json.loads(res_empty.text)
        self.assertEqual(empty.get('total'), 0)
        self.assertEqual(empty.get('items'), [])

        png_b64 = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        )
        banner = self.env['order_bridge.banner'].create({
            'title': 'Banner OB',
            'company_id': self.env.company.id,
            'image': png_b64,
            'active': True,
        })
        res = self.url_open('/api/order_bridge/banners', timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertEqual(data.get('total'), 1)
        items = data.get('items') or []
        self.assertEqual(len(items), 1)
        row = items[0]
        self.assertEqual(row.get('title'), 'Banner OB')
        self.assertTrue(row.get('image_url'))
        self.assertTrue(row.get('image_thumbnail_url'))
        self.assertIn(f'/web/image/order_bridge.banner/{banner.id}/image/512x0', row['image_url'])
        self.assertIn(f'/web/image/order_bridge.banner/{banner.id}/image/128x128', row['image_thumbnail_url'])
        parsed = urlparse(row['image_url'])
        path = parsed.path
        if parsed.query:
            path = f'{path}?{parsed.query}'
        img_res = self.url_open(path, timeout=60)
        self.assertEqual(img_res.status_code, 200, img_res.text)
        self.assertIn('image', (img_res.headers.get('Content-Type') or '').lower())

    def test_products_invalid_category_id_returns_400(self):
        key = str(uuid.uuid4())
        reg = self.url_open(
            '/api/order_bridge/register',
            data=json.dumps({'phone': '60011333', 'device_key': key}),
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
