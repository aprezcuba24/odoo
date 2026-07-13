# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiOtherCostReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cost_company = cls.env['res.company'].create({
            'name': 'BI Other Cost Report Test Co',
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

    def test_other_cost_report_includes_confirmed_cost(self):
        cost = self._create_cost({
            'name': 'Alquiler test',
            'date': fields.Date.today(),
            'amount': 500.0,
            'category_id': self.fixed_category.id,
        })
        cost.action_confirm()

        report = self.env['bi.other.cost.report'].search([
            ('name', '=', 'Alquiler test'),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.category_id, self.fixed_category)
        self.assertAlmostEqual(report.amount, 500.0)

    def test_other_cost_report_includes_supply_cost(self):
        cost = self._create_cost({
            'name': 'Consumo empaque',
            'date': fields.Date.today(),
            'category_id': self.supply_category.id,
            'supply_id': self.supply.id,
            'quantity': 5.0,
        })
        cost.action_confirm()

        report = self.env['bi.other.cost.report'].search([
            ('name', '=', 'Consumo empaque'),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.supply_id, self.supply)
        self.assertAlmostEqual(report.quantity, 5.0)
        self.assertAlmostEqual(report.amount, 10.0)

    def test_other_cost_report_excludes_draft_costs(self):
        self._create_cost({
            'name': 'Gasto borrador',
            'date': fields.Date.today(),
            'amount': 100.0,
            'category_id': self.fixed_category.id,
        })
        report = self.env['bi.other.cost.report'].search([
            ('name', '=', 'Gasto borrador'),
        ])
        self.assertFalse(report)

    def test_other_cost_report_filters_by_date(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        previous_month = month_start - relativedelta(months=1)

        current = self._create_cost({
            'name': 'Gasto mes actual',
            'date': month_start,
            'amount': 200.0,
            'category_id': self.fixed_category.id,
        })
        current.action_confirm()

        previous = self._create_cost({
            'name': 'Gasto mes anterior',
            'date': previous_month,
            'amount': 300.0,
            'category_id': self.fixed_category.id,
        })
        previous.action_confirm()

        report_data = self.env['bi.other.cost.report'].read_group(
            domain=[
                ('company_id', '=', self.cost_company.id),
                ('category_id', '=', self.fixed_category.id),
                ('date', '>=', month_start),
                ('date', '<', month_start + relativedelta(months=1)),
            ],
            fields=['amount'],
            groupby=['category_id'],
        )
        self.assertEqual(len(report_data), 1)
        self.assertAlmostEqual(report_data[0]['amount'], 200.0)

        all_data = self.env['bi.other.cost.report'].read_group(
            domain=[
                ('company_id', '=', self.cost_company.id),
                ('category_id', '=', self.fixed_category.id),
            ],
            fields=['amount'],
            groupby=['category_id'],
        )
        self.assertAlmostEqual(all_data[0]['amount'], 500.0)
