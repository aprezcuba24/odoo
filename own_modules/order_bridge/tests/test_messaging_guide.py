# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import fields
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.utils.constant import (
    STATE_NEGOTIATING,
    STATE_READY_FOR_DELIVERY,
    STATE_REVIEWING,
)
from odoo.addons.order_bridge.utils.order_contact import (
    delivery_address_text,
    order_phone,
)


@tagged('post_install', '-at_install')
class TestOrderBridgeMessagingGuide(TransactionCase):
    def _create_store_order(
        self, *, device_key, phone, street='Calle 1', qty=1.0, list_price=100.0, origin='app',
    ):
        partner = self.env['res.partner'].create({
            'name': f'Cliente {phone}',
            'phone': phone,
        })
        mun = self.env['order_bridge.municipality'].create({'name': f'Mun {device_key}'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': f'Barrio {device_key}',
            'municipality_id': mun.id,
        })
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': street,
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'state': 'La Habana',
        })
        device = self.env['order_bridge.device'].create({
            'device_key': device_key,
            'partner_id': partner.id,
            'phone': partner.phone,
        })
        product = self.env['product.product'].create({
            'name': f'Producto {device_key}',
            'sale_ok': True,
            'list_price': list_price,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': origin,
            'order_bridge_device_id': device.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': qty}),
            ],
        })
        return order, product

    def test_order_contact_helpers(self):
        order, _product = self._create_store_order(
            device_key='mg-contact',
            phone='+53555000111',
            street='Calle Principal 10',
        )
        self.assertEqual(order_phone(order), '+53555000111')
        address = delivery_address_text(order)
        self.assertIn('Calle Principal 10', address)
        self.assertIn('Barrio mg-contact. Mun mg-contact', address)
        self.assertIn('La Habana', address)

    def test_prepare_messaging_generates_pdf_without_state_change(self):
        order_a, _ = self._create_store_order(device_key='mg-a', phone='+53555000221')
        order_b, _ = self._create_store_order(device_key='mg-b', phone='+53555000222')
        order_c, _ = self._create_store_order(device_key='mg-c', phone='+53555000223')
        (order_a | order_b).write({'order_bridge_store_state': STATE_READY_FOR_DELIVERY})

        result = (order_a | order_b).action_order_bridge_prepare_messaging()
        self.assertIn('pdf_base64', result)
        self.assertTrue(result['pdf_base64'])
        self.assertEqual(result.get('mimetype'), 'application/pdf')
        self.assertRegex(
            result['filename'],
            r'^Guia_mensajeria_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.pdf$',
        )
        pdf_bytes = base64.b64decode(result['pdf_base64'])
        self.assertTrue(pdf_bytes)  # binary payload (PDF when wkhtmltopdf is available)
        self.assertEqual(order_a.order_bridge_store_state, STATE_READY_FOR_DELIVERY)
        self.assertEqual(order_b.order_bridge_store_state, STATE_READY_FOR_DELIVERY)
        self.assertEqual(order_c.order_bridge_store_state, STATE_REVIEWING)

    def test_prepare_messaging_rejects_invalid_state(self):
        order_reviewing, _ = self._create_store_order(device_key='mg-ok', phone='+53555000331')
        order_negotiating, _ = self._create_store_order(device_key='mg-bad', phone='+53555000332')
        order_negotiating.write({'order_bridge_store_state': STATE_NEGOTIATING})

        with self.assertRaises(UserError):
            (order_reviewing | order_negotiating).action_order_bridge_prepare_messaging()
        self.assertEqual(order_reviewing.order_bridge_store_state, STATE_REVIEWING)
        self.assertEqual(order_negotiating.order_bridge_store_state, STATE_NEGOTIATING)

    def test_prepare_messaging_rejects_non_store_order(self):
        partner = self.env['res.partner'].create({'name': 'Sin tienda', 'phone': '+53555000441'})
        product = self.env['product.product'].create({
            'name': 'Producto sin tienda',
            'sale_ok': True,
            'list_price': 50.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 1})],
        })
        with self.assertRaises(UserError):
            order.action_order_bridge_prepare_messaging()

    def test_messaging_guide_report_html_content(self):
        order, product = self._create_store_order(
            device_key='mg-pdf',
            phone='+53555000551',
            street='Avenida Central 5',
            qty=2.0,
            list_price=250.0,
        )
        html = self.env['ir.actions.report']._render_qweb_html(
            'order_bridge.report_messaging_guide',
            order.ids,
            data={'generated_at': '13/10/2026 11:16'},
        )[0]
        if isinstance(html, bytes):
            html = html.decode()
        self.assertIn(order.company_id.name, html)
        self.assertIn('Guía de mensajería', html)
        self.assertIn('13/10/2026 11:16', html)
        self.assertIn(order.partner_id.name, html)
        self.assertIn('+53555000551', html)
        self.assertIn('Avenida Central 5', html)
        self.assertIn(product.name, html)
        self.assertIn('Total a pagar', html)
        self.assertIn(str(order.amount_total).split('.')[0], html)
        self.assertIn('Creado:', html)
        created_at = fields.Datetime.context_timestamp(order, order.create_date)
        self.assertIn(created_at.strftime('%d/%m/%Y %H:%M'), html)
        self.assertNotIn('Pedido creado por el administrador.', html)
        self.assertNotIn('Notas para el mensajero', html)

        self.env['order_bridge.delivery.note'].create({
            'order_id': order.id,
            'author': 'admin',
            'body': 'Llamar antes de llegar',
        })
        html_notes = self.env['ir.actions.report']._render_qweb_html(
            'order_bridge.report_messaging_guide',
            order.ids,
            data={'generated_at': '13/10/2026 11:16'},
        )[0]
        if isinstance(html_notes, bytes):
            html_notes = html_notes.decode()
        self.assertIn('Notas para el mensajero', html_notes)
        self.assertIn('Llamar antes de llegar', html_notes)

        admin_order, _admin_product = self._create_store_order(
            device_key='mg-admin',
            phone='+53555000552',
            origin='admin',
        )
        admin_html = self.env['ir.actions.report']._render_qweb_html(
            'order_bridge.report_messaging_guide',
            admin_order.ids,
            data={'generated_at': '13/10/2026 11:16'},
        )[0]
        if isinstance(admin_html, bytes):
            admin_html = admin_html.decode()
        self.assertIn('Pedido creado por el administrador.', admin_html)
        self.assertIn('Creado:', admin_html)
