# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiOtherCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cost_company = cls.env['res.company'].create({
            'name': 'BI Other Cost Test Co',
        })
        cls.fixed_category = cls.env.ref('bi_analytics.cost_category_fixed')
        cls.supply_category = cls.env.ref('bi_analytics.cost_category_supply')
        cls.supply = cls.env['bi.supply'].with_company(cls.cost_company).create({
            'name': 'BI Test Supply',
            'unit': 'unidad',
            'cost': 2.0,
            'company_id': cls.cost_company.id,
            'currency_id': cls.cost_company.currency_id.id,
        })

    def _create_cost(self, values):
        values.setdefault('company_id', self.cost_company.id)
        values.setdefault('currency_id', self.cost_company.currency_id.id)
        return self.env['bi.other.cost'].create(values)

    def test_other_cost_confirm_and_draft(self):
        cost = self._create_cost({
            'name': 'Alquiler test',
            'date': fields.Date.today(),
            'amount': 500.0,
            'category_id': self.fixed_category.id,
        })
        self.assertEqual(cost.state, 'draft')
        cost.action_confirm()
        self.assertEqual(cost.state, 'confirmed')
        cost.action_draft()
        self.assertEqual(cost.state, 'draft')

    def test_other_cost_excludes_draft_from_profitability(self):
        month_start = fields.Date.today().replace(day=1)
        self._create_cost({
            'name': 'Gasto borrador',
            'date': month_start,
            'amount': 100.0,
            'category_id': self.fixed_category.id,
        })
        confirmed = self._create_cost({
            'name': 'Gasto confirmado',
            'date': month_start,
            'amount': 200.0,
            'category_id': self.fixed_category.id,
        })
        confirmed.action_confirm()

        report = self.env['bi.profitability.report'].search([
            ('date', '=', month_start),
            ('company_id', '=', self.cost_company.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.other_cost_amount, 200.0)

    def test_supply_cost_requires_supply_and_quantity(self):
        with self.assertRaises(ValidationError):
            self._create_cost({
                'name': 'Insumo sin insumo',
                'date': fields.Date.today(),
                'category_id': self.supply_category.id,
            })

    def test_supply_cost_computes_amount_from_quantity(self):
        cost = self._create_cost({
            'date': fields.Date.today(),
            'category_id': self.supply_category.id,
            'supply_id': self.supply.id,
            'quantity': 10.0,
        })
        self.assertAlmostEqual(cost.amount, 20.0)
        self.assertEqual(cost.name, 'BI Test Supply (10 unidad)')

    def test_supply_cost_auto_description_without_name(self):
        cost = self._create_cost({
            'date': fields.Date.today(),
            'category_id': self.supply_category.id,
            'supply_id': self.supply.id,
            'quantity': 3.0,
        })
        self.assertEqual(cost.name, 'BI Test Supply (3 unidad)')

    def test_fixed_cost_rejects_supply(self):
        with self.assertRaises(ValidationError):
            self._create_cost({
                'name': 'Fijo con insumo',
                'date': fields.Date.today(),
                'amount': 50.0,
                'category_id': self.fixed_category.id,
                'supply_id': self.supply.id,
            })

    def test_other_cost_rejects_non_positive_amount(self):
        with self.assertRaises(ValidationError):
            self._create_cost({
                'name': 'Importe inválido',
                'date': fields.Date.today(),
                'amount': 0.0,
                'category_id': self.fixed_category.id,
            })
