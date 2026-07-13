# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiSupplyEntry(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supply_company = cls.env['res.company'].create({
            'name': 'BI Supply Entry Test Co',
        })
        cls.supply = cls.env['bi.supply'].with_company(cls.supply_company).create({
            'name': 'Caja de cartón',
            'unit': 'unidad',
            'company_id': cls.supply_company.id,
            'currency_id': cls.supply_company.currency_id.id,
        })

    def _create_entry(self, quantity, unit_cost, date=None):
        return self.env['bi.supply.entry'].create({
            'supply_id': self.supply.id,
            'date': date or fields.Date.today(),
            'quantity': quantity,
            'unit_cost': unit_cost,
            'company_id': self.supply_company.id,
            'currency_id': self.supply_company.currency_id.id,
        })

    def test_entry_increases_stock_and_average_cost(self):
        self._create_entry(10.0, 2.0)
        self._create_entry(10.0, 4.0)
        self.assertAlmostEqual(self.supply.qty_available, 20.0)
        self.assertAlmostEqual(self.supply.average_cost, 3.0)

    def test_entry_rejects_non_positive_values(self):
        with self.assertRaises(ValidationError):
            self._create_entry(0.0, 2.0)
        with self.assertRaises(ValidationError):
            self._create_entry(10.0, 0.0)

    def test_entry_unlink_recomputes_stock(self):
        entry = self._create_entry(10.0, 2.0)
        self.assertAlmostEqual(self.supply.qty_available, 10.0)
        entry.unlink()
        self.assertAlmostEqual(self.supply.qty_available, 0.0)
        self.assertAlmostEqual(self.supply.average_cost, 0.0)

    def test_entries_with_different_dates(self):
        self._create_entry(5.0, 2.0, fields.Date.to_date('2026-01-01'))
        self._create_entry(5.0, 4.0, fields.Date.to_date('2026-02-01'))
        self.assertAlmostEqual(self.supply.qty_available, 10.0)
        self.assertAlmostEqual(self.supply.average_cost, 3.0)
