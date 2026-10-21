# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from urllib.parse import quote

from odoo.fields import Command
from odoo.tests.common import HttpCase, tagged

from odoo.addons.order_bridge.utils.constant import (
    STATE_CANCELED,
    STATE_DELIVERED,
    STATE_READY_FOR_DELIVERY,
    STATE_REVIEWING,
)


@tagged('post_install', '-at_install')
class TestMobileDeliveriesApi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('es_ES')
        cls.messenger = cls.env['order_bridge.messenger'].create({
            'name': 'Mensajero Test',
        })
        cls.api_key = cls.messenger.api_key
        cls.other_messenger = cls.env['order_bridge.messenger'].create({
            'name': 'Otro Mensajero',
        })

    def _auth_headers(self, key=None):
        return {
            'Accept': 'application/json',
            'X-Api-Key': key if key is not None else self.api_key,
        }

    def _create_store_order(
        self,
        *,
        phone='+53555001003',
        street='Avenida 5ta #7802, Miramar',
        name='Luis Fernández',
        latitude=0.0,
        longitude=0.0,
        messenger=None,
        list_price=120.0,
        product_name='Arroz',
        store_state=STATE_READY_FOR_DELIVERY,
    ):
        partner = self.env['res.partner'].create({
            'name': name,
            'phone': phone,
        })
        mun = self.env['order_bridge.municipality'].create({'name': f'Mun {phone}'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': f'Barrio {phone}',
            'municipality_id': mun.id,
        })
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': street,
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'state': 'La Habana',
            'latitude': latitude,
            'longitude': longitude,
        })
        product = self.env['product.product'].create({
            'name': product_name,
            'sale_ok': True,
            'list_price': list_price,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_bridge_messenger_id': (messenger or self.messenger).id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1}),
            ],
        })
        if store_state != STATE_REVIEWING:
            order.write({'order_bridge_store_state': store_state})
        return order

    def _create_ready_order(self, **kwargs):
        return self._create_store_order(store_state=STATE_READY_FOR_DELIVERY, **kwargs)

    def test_get_deliveries_requires_api_key(self):
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers={'Accept': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)

        res_bad = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers('not-a-valid-key'),
            timeout=60,
        )
        self.assertEqual(res_bad.status_code, 401, res_bad.text)

    def test_get_deliveries_returns_top_level_array(self):
        order = self._create_ready_order(latitude=23.18, longitude=-82.288)
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        item = data[0]
        for key in (
            'identifier',
            'reference',
            'customerName',
            'customerPhone',
            'address',
            'date',
        ):
            self.assertIsInstance(item[key], str, key)
        self.assertEqual(item['identifier'], str(order.id))
        self.assertEqual(item['reference'], order.name)
        self.assertEqual(item['customerName'], 'Luis Fernández')
        self.assertEqual(item['customerPhone'], '+53555001003')
        self.assertIn('Avenida 5ta #7802, Miramar', item['address'])
        self.assertRegex(item['date'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertIsInstance(item['point'], dict)
        self.assertIsInstance(item['point']['longitude'], (int, float))
        self.assertIsInstance(item['point']['latitude'], (int, float))
        self.assertAlmostEqual(item['point']['longitude'], -82.288, places=5)
        self.assertAlmostEqual(item['point']['latitude'], 23.18, places=5)
        self.assertIsInstance(item['description'], str)
        self.assertIn('Arroz', item['description'])
        self.assertEqual(item['notes'], [])
        self.assertNotIn('status', item)
        self.assertNotIn('syncStatus', item)

    def test_get_deliveries_point_null_when_unset(self):
        self._create_ready_order(latitude=0.0, longitude=0.0)
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        item = json.loads(res.text)[0]
        self.assertIsNone(item['point'])

    def test_get_deliveries_point_null_when_incomplete(self):
        self._create_ready_order(latitude=23.1, longitude=0.0)
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIsNone(json.loads(res.text)[0]['point'])

    def test_get_deliveries_empty_and_filters_by_messenger(self):
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(json.loads(res.text), [])

        mine = self._create_ready_order(phone='+53555002001')
        other = self._create_ready_order(
            phone='+53555002002',
            messenger=self.other_messenger,
        )
        reviewing = self._create_store_order(
            phone='+53555002003',
            store_state=STATE_REVIEWING,
        )

        res2 = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res2.status_code, 200, res2.text)
        ids = {row['identifier'] for row in json.loads(res2.text)}
        self.assertEqual(ids, {str(mine.id)})
        self.assertNotIn(str(other.id), ids)
        self.assertNotIn(str(reviewing.id), ids)

    def test_post_delivered_requires_api_key(self):
        order = self._create_ready_order()
        url = f'/api/mobile/v1/deliveries/{order.id}/delivered'
        payload = json.dumps({'deviceTimestamp': '2026-10-15T11:00:00.000Z'})
        res = self.url_open(
            url,
            data=payload,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)

    def test_post_delivered_success_idempotent_and_removed_from_get(self):
        order = self._create_ready_order()
        url = f'/api/mobile/v1/deliveries/{quote(str(order.id), safe="")}/delivered'
        headers = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        payload = json.dumps({'deviceTimestamp': '2026-10-15T11:00:00.000Z'})

        res = self.url_open(url, data=payload, headers=headers, timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        self.assertIn('serverReceivedAt', data)
        self.assertIsInstance(data['serverReceivedAt'], str)
        self.assertTrue(data['serverReceivedAt'])
        first_stamp = data['serverReceivedAt']

        order.invalidate_recordset()
        self.assertEqual(order.order_bridge_store_state, STATE_DELIVERED)
        self.assertEqual(order.order_bridge_delivery_received_at, first_stamp)
        self.assertEqual(order.order_bridge_delivery_device_at, '2026-10-15T11:00:00.000Z')

        res2 = self.url_open(url, data=payload, headers=headers, timeout=60)
        self.assertEqual(res2.status_code, 200, res2.text)
        self.assertEqual(json.loads(res2.text)['serverReceivedAt'], first_stamp)
        order.invalidate_recordset()
        self.assertEqual(order.order_bridge_store_state, STATE_DELIVERED)

        res_get = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res_get.status_code, 200, res_get.text)
        self.assertEqual(json.loads(res_get.text), [])

    def test_post_delivered_404_for_unknown_or_foreign_order(self):
        headers = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        payload = json.dumps({'deviceTimestamp': '2026-10-15T11:00:00.000Z'})

        res_missing = self.url_open(
            '/api/mobile/v1/deliveries/999999999/delivered',
            data=payload,
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res_missing.status_code, 404, res_missing.text)

        foreign = self._create_ready_order(
            phone='+53555003001',
            messenger=self.other_messenger,
        )
        res_foreign = self.url_open(
            f'/api/mobile/v1/deliveries/{foreign.id}/delivered',
            data=payload,
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res_foreign.status_code, 404, res_foreign.text)

    def test_post_delivered_400_invalid_body(self):
        order = self._create_ready_order()
        headers = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        res = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/delivered',
            data=json.dumps({}),
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res.status_code, 400, res.text)

        res2 = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/delivered',
            data=json.dumps({'deviceTimestamp': 'not-a-date'}),
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res2.status_code, 400, res2.text)

    def test_post_delivered_409_when_not_ready(self):
        order = self._create_ready_order()
        order.write({'order_bridge_store_state': STATE_CANCELED})
        headers = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        res = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/delivered',
            data=json.dumps({'deviceTimestamp': '2026-10-15T11:00:00.000Z'}),
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res.status_code, 409, res.text)

    def test_inactive_messenger_gets_401(self):
        self.messenger.active = False
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 401, res.text)

    def test_get_deliveries_includes_admin_and_messenger_notes(self):
        order = self._create_ready_order()
        self.env['order_bridge.delivery.note'].create({
            'order_id': order.id,
            'author': 'admin',
            'body': 'Tocar el timbre dos veces',
        })
        self.env['order_bridge.delivery.note'].create({
            'order_id': order.id,
            'author': 'messenger',
            'body': 'Cliente no estaba',
            'messenger_id': self.messenger.id,
        })
        res = self.url_open(
            '/api/mobile/v1/deliveries',
            headers=self._auth_headers(),
            timeout=60,
        )
        self.assertEqual(res.status_code, 200, res.text)
        notes = json.loads(res.text)[0]['notes']
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]['author'], 'admin')
        self.assertEqual(notes[0]['body'], 'Tocar el timbre dos veces')
        self.assertRegex(notes[0]['createdAt'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
        self.assertEqual(notes[1]['author'], 'messenger')
        self.assertEqual(notes[1]['body'], 'Cliente no estaba')

    def test_post_note_success_marks_unread(self):
        order = self._create_ready_order()
        self.assertFalse(order.order_bridge_unread_messenger_note)
        headers = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        res = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/notes',
            data=json.dumps({'note': '  Dejé el paquete en portería  '}),
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res.status_code, 201, res.text)
        data = json.loads(res.text)
        self.assertEqual(data['author'], 'messenger')
        self.assertEqual(data['body'], 'Dejé el paquete en portería')
        self.assertRegex(data['createdAt'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')

        order.invalidate_recordset()
        self.assertTrue(order.order_bridge_unread_messenger_note)
        self.assertEqual(len(order.order_bridge_delivery_note_ids), 1)
        note = order.order_bridge_delivery_note_ids[0]
        self.assertEqual(note.author, 'messenger')
        self.assertFalse(note.reviewed)
        self.assertEqual(note.messenger_id, self.messenger)

        order.action_order_bridge_mark_messenger_notes_reviewed()
        order.invalidate_recordset()
        self.assertFalse(order.order_bridge_unread_messenger_note)
        self.assertTrue(note.reviewed)

    def test_post_note_rejects_foreign_messenger_and_invalid_body(self):
        order = self._create_ready_order()
        headers = {
            **self._auth_headers(self.other_messenger.api_key),
            'Content-Type': 'application/json',
        }
        res_foreign = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/notes',
            data=json.dumps({'note': 'hola'}),
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res_foreign.status_code, 404, res_foreign.text)

        headers_ok = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        res_empty = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/notes',
            data=json.dumps({'note': '   '}),
            headers=headers_ok,
            timeout=60,
        )
        self.assertEqual(res_empty.status_code, 400, res_empty.text)
        self.assertEqual(json.loads(res_empty.text)['error'], 'invalid_note')

        res_missing = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/notes',
            data=json.dumps({}),
            headers=headers_ok,
            timeout=60,
        )
        self.assertEqual(res_missing.status_code, 400, res_missing.text)

    def test_post_note_409_when_reviewing(self):
        order = self._create_store_order(store_state=STATE_REVIEWING)
        headers = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        res = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/notes',
            data=json.dumps({'note': 'nota'}),
            headers=headers,
            timeout=60,
        )
        # Not in GET list; POST still finds the order but state conflicts.
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(json.loads(res.text)['error'], 'conflict')

    def test_post_note_allowed_when_delivered(self):
        order = self._create_ready_order()
        order.write({'order_bridge_store_state': STATE_DELIVERED})
        headers = {
            **self._auth_headers(),
            'Content-Type': 'application/json',
        }
        res = self.url_open(
            f'/api/mobile/v1/deliveries/{order.id}/notes',
            data=json.dumps({'note': 'Entregué y cobré'}),
            headers=headers,
            timeout=60,
        )
        self.assertEqual(res.status_code, 201, res.text)
        order.invalidate_recordset()
        self.assertTrue(order.order_bridge_unread_messenger_note)
