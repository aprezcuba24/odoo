# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeAdminStock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente stock admin',
            'phone': '+529991113344',
        })
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1,
        )
        assert cls.warehouse, 'Se requiere un almacén para la compañía de prueba'
        cls.Location = cls.env['stock.location']
        cls.Quant = cls.env['stock.quant'].with_context(inventory_mode=True)
        cls.precision = cls.env['decimal.precision'].precision_get('Product Unit')

    def _storable_product(self, name):
        tmpl = self.env['product.template'].create({
            'name': name,
            'sale_ok': True,
            'is_storable': True,
            'list_price': 10.0,
        })
        return tmpl.product_variant_id

    def _stock_on_two_shelves(self, product, qty_a=3.0, qty_b=7.0):
        subloc_a = self.Location.create({
            'name': f'{product.name} Shelf A',
            'location_id': self.warehouse.lot_stock_id.id,
            'usage': 'internal',
        })
        subloc_b = self.Location.create({
            'name': f'{product.name} Shelf B',
            'location_id': self.warehouse.lot_stock_id.id,
            'usage': 'internal',
        })
        self.Quant.create({
            'product_id': product.id,
            'location_id': subloc_a.id,
            'inventory_quantity': qty_a,
        }).action_apply_inventory()
        self.Quant.create({
            'product_id': product.id,
            'location_id': subloc_b.id,
            'inventory_quantity': qty_b,
        }).action_apply_inventory()
        return subloc_a, subloc_b

    def test_admin_create_reserves_across_sublocations(self):
        product = self._storable_product('Admin stock two shelves')
        subloc_a, subloc_b = self._stock_on_two_shelves(product)
        free_before = product.with_context(warehouse_id=self.warehouse.id).free_qty
        self.assertEqual(free_before, 10.0)

        order = self.env['sale.order'].with_context(order_bridge_admin_create=True).create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 8.0})],
        })
        self.assertEqual(order.order_bridge_origin, 'admin')
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.warehouse_id, self.warehouse)

        stock_locs = self.Location.search([
            ('id', 'child_of', self.warehouse.view_location_id.id),
        ])
        stock_moves = order.picking_ids.move_ids.filtered(
            lambda m: m.product_id == product and m.location_id in stock_locs,
        )
        self.assertTrue(stock_moves)
        move_lines = stock_moves.move_line_ids
        self.assertTrue(move_lines)
        reserved_qty = sum(move_lines.mapped('quantity'))
        self.assertAlmostEqual(reserved_qty, 8.0, places=self.precision)
        reserved_locations = move_lines.location_id
        self.assertIn(subloc_a, reserved_locations)
        self.assertIn(subloc_b, reserved_locations)

        free_after = product.with_context(warehouse_id=self.warehouse.id).free_qty
        self.assertAlmostEqual(free_after, 2.0, places=self.precision)

    def test_admin_create_rejects_insufficient_stock(self):
        product = self._storable_product('Admin stock insufficient')
        self._stock_on_two_shelves(product, qty_a=1.0, qty_b=1.0)
        SaleOrder = self.env['sale.order'].with_context(order_bridge_admin_create=True)
        with self.assertRaises(UserError) as err:
            SaleOrder.create({
                'partner_id': self.partner.id,
                'company_id': self.company.id,
                'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 5.0})],
            })
        self.assertIn('Stock insuficiente', err.exception.args[0])
        self.assertFalse(SaleOrder.search([
            ('partner_id', '=', self.partner.id),
            ('order_bridge_origin', '=', 'admin'),
            ('order_line.product_id', '=', product.id),
        ]))

    def test_admin_write_lines_confirms_and_reserves(self):
        product = self._storable_product('Admin stock write lines')
        self._stock_on_two_shelves(product)
        order = self.env['sale.order'].with_context(order_bridge_admin_create=True).create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
        })
        self.assertEqual(order.state, 'draft')

        order.write({
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 8.0})],
        })
        self.assertEqual(order.state, 'sale')
        free_after = product.with_context(warehouse_id=self.warehouse.id).free_qty
        self.assertAlmostEqual(free_after, 2.0, places=self.precision)

    def test_standard_quotation_not_blocked_by_store_stock_rule(self):
        product = self._storable_product('Std sale no stock check')
        # No inventory: Tienda Apk would reject; standard quotation must still create.
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 5.0})],
        })
        self.assertFalse(order.order_bridge_origin)
        self.assertEqual(order.state, 'draft')
