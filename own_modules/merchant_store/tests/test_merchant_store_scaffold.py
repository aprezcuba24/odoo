# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMerchantStoreScaffold(TransactionCase):
    def test_root_menu_and_groups_exist(self):
        menu = self.env.ref('merchant_store.menu_merchant_store_root')
        self.assertEqual(menu.name, 'Comercios')
        self.assertFalse(menu.parent_id)

        user_group = self.env.ref('merchant_store.group_merchant_store_user')
        manager_group = self.env.ref('merchant_store.group_merchant_store_manager')
        salesman = self.env.ref('sales_team.group_sale_salesman')
        sale_manager = self.env.ref('sales_team.group_sale_manager')

        self.assertIn(salesman, user_group.implied_ids)
        self.assertIn(user_group, manager_group.implied_ids)
        self.assertIn(sale_manager, manager_group.implied_ids)
