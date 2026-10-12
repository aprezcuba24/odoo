# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWhatsappPublisherProducts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1,
        )
        assert cls.warehouse, 'Se necesita un almacén para la compañía de prueba'

    def _create_storable(self, name, qty=10.0, **vals):
        tmpl = self.env['product.template'].create({
            'name': name,
            'sale_ok': True,
            'is_storable': True,
            'list_price': 25.0,
            **vals,
        })
        product = tmpl.product_variant_id
        if qty:
            self.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': product.id,
                'location_id': self.warehouse.lot_stock_id.id,
                'inventory_quantity': qty,
            }).action_apply_inventory()
        return product

    def test_includes_storable_with_stock_and_visibility_flag(self):
        visible = self._create_storable(
            'WA pub visible', order_bridge_visible=True, default_code='WA-VIS',
        )
        hidden = self._create_storable(
            'WA pub hidden', order_bridge_visible=False, default_code='WA-HID',
        )
        rows = self.env['product.product'].get_whatsapp_publisher_products()
        by_id = {row['id']: row for row in rows}

        self.assertIn(visible.id, by_id)
        self.assertTrue(by_id[visible.id]['order_bridge_visible'])
        self.assertEqual(by_id[visible.id]['default_code'], 'WA-VIS')
        self.assertTrue(by_id[visible.id]['uom_name'])
        self.assertGreater(by_id[visible.id]['free_qty'], 0)

        self.assertIn(hidden.id, by_id)
        self.assertFalse(by_id[hidden.id]['order_bridge_visible'])
        self.assertEqual(by_id[hidden.id]['default_code'], 'WA-HID')

    def test_excludes_no_stock_service_and_not_saleable(self):
        no_stock = self._create_storable(
            'WA pub no stock', qty=0.0, order_bridge_visible=True,
        )
        service = self.env['product.template'].create({
            'name': 'WA pub service',
            'sale_ok': True,
            'type': 'service',
            'list_price': 5.0,
            'order_bridge_visible': True,
        }).product_variant_id
        not_sale = self._create_storable(
            'WA pub not sale', sale_ok=False, order_bridge_visible=True,
        )

        ids = {row['id'] for row in self.env['product.product'].get_whatsapp_publisher_products()}
        self.assertNotIn(no_stock.id, ids)
        self.assertNotIn(service.id, ids)
        self.assertNotIn(not_sale.id, ids)
