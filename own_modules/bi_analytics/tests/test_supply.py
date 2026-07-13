# Part of Odoo. See LICENSE file for full copyright and licensing details.

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
            'cost': 2.5,
            'company_id': self.supply_company.id,
            'currency_id': self.supply_company.currency_id.id,
        })
        self.assertEqual(supply.name, 'Caja de cartón')
        self.assertEqual(supply.unit, 'unidad')
        self.assertAlmostEqual(supply.cost, 2.5)

    def test_supply_rejects_non_positive_cost(self):
        with self.assertRaises(ValidationError):
            self.env['bi.supply'].with_company(self.supply_company).create({
                'name': 'Insumo inválido',
                'unit': 'kg',
                'cost': 0.0,
                'company_id': self.supply_company.id,
                'currency_id': self.supply_company.currency_id.id,
            })
