# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPartnerMapPoint(TransactionCase):
    def _create_municipality_neighborhood(self, suffix):
        mun = self.env['order_bridge.municipality'].create({'name': f'Mun {suffix}'})
        nbh = self.env['order_bridge.neighborhood'].create({
            'name': f'Barrio {suffix}',
            'municipality_id': mun.id,
        })
        return mun, nbh

    def test_has_map_point_false_without_address(self):
        partner = self.env['res.partner'].create({'name': 'Sin dirección mapa'})
        self.assertFalse(partner.order_bridge_has_map_point)

        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
        })
        self.assertFalse(order.order_bridge_partner_has_map_point)

    def test_has_map_point_false_when_coords_zero(self):
        partner = self.env['res.partner'].create({'name': 'Coords cero'})
        mun, nbh = self._create_municipality_neighborhood('cero')
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Calle 1',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'latitude': 0.0,
            'longitude': 0.0,
        })
        self.assertFalse(partner.order_bridge_has_map_point)

        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
        })
        self.assertFalse(order.order_bridge_partner_has_map_point)

    def test_has_map_point_false_when_longitude_zero(self):
        partner = self.env['res.partner'].create({'name': 'Lon cero'})
        mun, nbh = self._create_municipality_neighborhood('lon0')
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Calle 2',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'latitude': 23.1,
            'longitude': 0.0,
        })
        self.assertFalse(partner.order_bridge_has_map_point)

    def test_has_map_point_true_with_valid_coords(self):
        partner = self.env['res.partner'].create({'name': 'Con mapa'})
        mun, nbh = self._create_municipality_neighborhood('ok')
        self.env['order_bridge.partner_address'].create({
            'partner_id': partner.id,
            'street': 'Calle 3',
            'municipality_id': mun.id,
            'neighborhood_id': nbh.id,
            'latitude': 23.18,
            'longitude': -82.288,
        })
        self.assertTrue(partner.order_bridge_has_map_point)

        product = self.env['product.product'].create({
            'name': 'Producto mapa',
            'sale_ok': True,
            'list_price': 10.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1}),
            ],
        })
        self.assertTrue(order.order_bridge_partner_has_map_point)
