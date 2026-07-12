# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiSupplyStockFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search([
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        cls.supply_product = cls.env['product.product'].create({
            'name': 'BI Test Packaging',
            'sale_ok': False,
            'purchase_ok': True,
            'type': 'consu',
            'is_storable': True,
            'standard_price': 2.0,
        })
        cls.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': cls.supply_product.id,
            'location_id': cls.warehouse.lot_stock_id.id,
            'inventory_quantity': 100.0,
        }).action_apply_inventory()

    def test_supply_scrap_creates_confirmed_other_cost(self):
        scrap = self.env['stock.scrap'].create({
            'product_id': self.supply_product.id,
            'scrap_qty': 10.0,
            'location_id': self.warehouse.lot_stock_id.id,
        })
        scrap.action_validate()

        self.assertEqual(scrap.state, 'done')
        self.assertTrue(scrap.bi_other_cost_id)
        self.assertEqual(scrap.bi_other_cost_id.state, 'confirmed')
        self.assertEqual(scrap.bi_other_cost_id.product_id, self.supply_product)
        self.assertAlmostEqual(scrap.bi_other_cost_id.amount, 20.0)

        month_start = fields.Date.to_date(scrap.date_done).replace(day=1)
        report = self.env['bi.profitability.report'].search([
            ('company_id', '=', self.env.company.id),
            ('date', '=', month_start),
        ])
        self.assertTrue(report)
        self.assertAlmostEqual(report.other_cost_amount, 20.0)
