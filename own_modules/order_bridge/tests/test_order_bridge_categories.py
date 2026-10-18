# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Tests for product.category ordering and permission model in order_bridge."""

import json

from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCategoryApiOrder(HttpCase):
    """GET /api/order_bridge/categories returns items in order_bridge_sequence order."""

    def setUp(self):
        super().setUp()
        # Clean slate: archive all visible products so only ours appear
        self.env['product.template'].sudo().search(
            [('order_bridge_visible', '=', True)]
        ).write({'order_bridge_visible': False})

    def test_categories_ordered_by_sequence(self):
        """Items in the API response follow order_bridge_sequence, then name."""
        categ_a = self.env['product.category'].sudo().create({
            'name': 'ZZ Última (secuencia baja)',
            'order_bridge_sequence': 1,
        })
        categ_b = self.env['product.category'].sudo().create({
            'name': 'AA Primera (secuencia alta)',
            'order_bridge_sequence': 99,
        })
        categ_c = self.env['product.category'].sudo().create({
            'name': 'MM Media (secuencia media)',
            'order_bridge_sequence': 50,
        })

        for categ in (categ_a, categ_b, categ_c):
            self.env['product.template'].sudo().create({
                'name': f'Producto categ {categ.id}',
                'sale_ok': True,
                'order_bridge_visible': True,
                'list_price': 1.0,
                'categ_id': categ.id,
            })

        res = self.url_open('/api/order_bridge/categories', timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        ids = [item['id'] for item in data['items']]

        # categ_a (seq=1) must come before categ_c (seq=50) before categ_b (seq=99)
        self.assertIn(categ_a.id, ids)
        self.assertIn(categ_b.id, ids)
        self.assertIn(categ_c.id, ids)
        pos_a = ids.index(categ_a.id)
        pos_c = ids.index(categ_c.id)
        pos_b = ids.index(categ_b.id)
        self.assertLess(pos_a, pos_c, 'seq=1 debe ir antes que seq=50')
        self.assertLess(pos_c, pos_b, 'seq=50 debe ir antes que seq=99')

    def test_categories_response_contains_sequence_field(self):
        """Each item in the response exposes the `sequence` field."""
        categ = self.env['product.category'].sudo().create({
            'name': 'Categ con secuencia 7',
            'order_bridge_sequence': 7,
        })
        self.env['product.template'].sudo().create({
            'name': 'Producto de categ 7',
            'sale_ok': True,
            'order_bridge_visible': True,
            'list_price': 1.0,
            'categ_id': categ.id,
        })
        res = self.url_open('/api/order_bridge/categories', timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        row = next((i for i in data['items'] if i['id'] == categ.id), None)
        self.assertIsNotNone(row, 'La categoría debe aparecer en la respuesta')
        self.assertIn('sequence', row, 'El campo sequence debe estar en el JSON')
        self.assertEqual(row['sequence'], 7)

    def test_equal_sequence_falls_back_to_name(self):
        """Categories with the same sequence are sorted alphabetically."""
        categ_x = self.env['product.category'].sudo().create({
            'name': 'Bebidas',
            'order_bridge_sequence': 10,
        })
        categ_y = self.env['product.category'].sudo().create({
            'name': 'Alimentos',
            'order_bridge_sequence': 10,
        })
        for categ in (categ_x, categ_y):
            self.env['product.template'].sudo().create({
                'name': f'Prod {categ.name}',
                'sale_ok': True,
                'order_bridge_visible': True,
                'list_price': 1.0,
                'categ_id': categ.id,
            })
        res = self.url_open('/api/order_bridge/categories', timeout=60)
        self.assertEqual(res.status_code, 200, res.text)
        data = json.loads(res.text)
        ids = [item['id'] for item in data['items']]
        pos_x = ids.index(categ_x.id)
        pos_y = ids.index(categ_y.id)
        # "Alimentos" < "Bebidas" alphabetically (by complete_name)
        self.assertLess(pos_y, pos_x, 'A igual secuencia, orden alfabético por complete_name')


@tagged('post_install', '-at_install')
class TestCategoryPermissions(TransactionCase):
    """product.category permission model enforced by order_bridge extension."""

    def setUp(self):
        super().setUp()
        # Create a salesman user (no product manager, no OB manager)
        Users = self.env['res.users'].sudo().with_context(no_reset_password=True)
        self.salesman_user = Users.create({
            'name': 'Vendedor OB Test',
            'login': 'ob_test_salesman@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('sales_team.group_sale_salesman').id,
            ])],
        })
        # Create an OB manager user
        self.ob_manager_user = Users.create({
            'name': 'OB Manager Test',
            'login': 'ob_test_manager@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('order_bridge.group_order_bridge_manager').id,
            ])],
        })
        self.categ = self.env['product.category'].sudo().create({
            'name': 'Categ permisos test',
            'order_bridge_sequence': 10,
        })

    def test_salesman_can_change_sequence(self):
        """Salesman may update order_bridge_sequence."""
        self.categ.with_user(self.salesman_user).write({'order_bridge_sequence': 5})
        self.assertEqual(self.categ.order_bridge_sequence, 5)

    def test_salesman_cannot_rename(self):
        """Salesman cannot rename a category (only managers can)."""
        with self.assertRaises(AccessError):
            self.categ.with_user(self.salesman_user).write({'name': 'Nombre cambiado'})

    def test_salesman_cannot_create_category(self):
        """Salesman cannot create a new category."""
        with self.assertRaises(AccessError):
            self.env['product.category'].with_user(self.salesman_user).create({
                'name': 'Nueva categoría por vendedor',
            })

    def test_salesman_cannot_delete_category(self):
        """Salesman cannot delete a category."""
        with self.assertRaises(AccessError):
            self.categ.with_user(self.salesman_user).unlink()

    def test_ob_manager_can_create_rename_delete(self):
        """OB manager can create, rename and delete categories."""
        new_categ = self.env['product.category'].with_user(self.ob_manager_user).create({
            'name': 'Categ creada por OB manager',
            'order_bridge_sequence': 20,
        })
        self.assertTrue(new_categ.id)
        new_categ.with_user(self.ob_manager_user).write({'name': 'Renombrada por OB manager'})
        self.assertEqual(new_categ.name, 'Renombrada por OB manager')
        new_categ.with_user(self.ob_manager_user).unlink()

    def test_ob_manager_can_change_sequence(self):
        """OB manager can also change the sequence."""
        self.categ.with_user(self.ob_manager_user).write({'order_bridge_sequence': 3})
        self.assertEqual(self.categ.order_bridge_sequence, 3)
