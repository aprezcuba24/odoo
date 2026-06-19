# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartnerOrderBridgeOrders(TransactionCase):
    def test_order_bridge_order_count_and_action_domain(self):
        partner = self.env['res.partner'].create({'name': 'Cliente filtro tienda'})
        SaleOrder = self.env['sale.order']
        normal_order = SaleOrder.create({'partner_id': partner.id})
        store_order = SaleOrder.create({
            'partner_id': partner.id,
            'order_bridge_origin': 'app',
        })

        self.assertEqual(partner.order_bridge_order_count, 1)

        action = partner.action_open_order_bridge_orders()
        domain = action['domain']
        matched = SaleOrder.search(domain)
        self.assertIn(store_order, matched)
        self.assertNotIn(normal_order, matched)

        list_view = self.env.ref('order_bridge.view_order_tree_order_bridge_store')
        self.assertEqual(action['views'], [(list_view.id, 'list'), (False, 'form')])
