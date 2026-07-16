# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiSupply(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supply_company = cls.env['res.company'].create({
            'name': 'BI Supply Test Co',
        })

    def test_supply_create(self):
        supply = self.env['bi.supply'].with_company(self.supply_company).create({
            'name': 'Caja de cartón',
            'unit': 'unidad',
            'company_id': self.supply_company.id,
            'currency_id': self.supply_company.currency_id.id,
        })
        self.assertEqual(supply.name, 'Caja de cartón')
        self.assertEqual(supply.unit, 'unidad')
        self.assertAlmostEqual(supply.average_cost, 0.0)
        self.assertAlmostEqual(supply.qty_available, 0.0)
