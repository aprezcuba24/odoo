# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWhatsappMessages(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Message = cls.env['order_bridge.whatsapp.message']
        cls.company = cls.env.company
        cls.other_company = cls.env['res.company'].create({'name': 'WA Msg Other Co'})

    def test_text_requires_body(self):
        with self.assertRaises(ValidationError):
            self.Message.create({
                'name': 'Vacío',
                'position': 'start',
                'body': '   ',
            })

    def test_get_publisher_messages_order_and_filters(self):
        self.Message.with_context(active_test=False).search([]).unlink()
        end_msg = self.Message.create({
            'name': 'Cierre',
            'position': 'end',
            'body': '¡Gracias! 🙏',
            'sequence': 5,
        })
        start_msg = self.Message.create({
            'name': 'Saludo',
            'position': 'start',
            'body': 'Hola 👋',
            'sequence': 20,
        })
        start_first = self.Message.create({
            'name': 'Intro',
            'position': 'start',
            'body': 'Catálogo del día',
            'sequence': 10,
        })
        archived = self.Message.create({
            'name': 'Archivado',
            'position': 'start',
            'body': 'No debe salir',
            'active': False,
        })
        other = self.Message.create({
            'name': 'Otra compañía',
            'position': 'start',
            'body': 'Otro tenant',
            'company_id': self.other_company.id,
        })

        rows = self.Message.get_whatsapp_publisher_messages()
        ids = [row['id'] for row in rows]

        self.assertEqual(ids, [start_first.id, start_msg.id, end_msg.id])
        self.assertNotIn(archived.id, ids)
        self.assertNotIn(other.id, ids)

        by_id = {row['id']: row for row in rows}
        self.assertEqual(by_id[start_msg.id]['kind'], 'text')
        self.assertEqual(by_id[start_msg.id]['text'], 'Hola 👋')
        self.assertEqual(by_id[start_msg.id]['position'], 'start')
