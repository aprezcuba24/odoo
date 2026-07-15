# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiProfitabilityReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('point_of_sale.group_pos_manager')
        cls.profitability_company = cls.env['res.company'].create({
            'name': 'BI Profitability Test Co',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'BI Profitability Customer',
            'company_id': cls.profitability_company.id,
        })
        cls.product = cls.env['product.product'].with_company(cls.profitability_company).create({
            'name': 'BI Profitability Product',
            'sale_ok': True,
            'list_price': 10.0,
            'standard_price': 4.0,
        })
        cls.pos_product = cls.env['product.product'].create({
            'name': 'BI Profitability POS Product',
            'sale_ok': True,
            'available_in_pos': True,
            'list_price': 10.0,
            'standard_price': 4.0,
            'taxes_id': False,
        })
        cls.pos_payment_method = cls.env['pos.payment.method'].create({
            'name': 'BI Profitability Bank',
            'receivable_account_id': cls.env.company.account_default_pos_receivable_account_id.id,
            'journal_id': cls.env['account.journal'].create({
                'name': 'BI Profitability Bank',
                'code': 'BIPR',
                'type': 'bank',
                'company_id': cls.env.company.id,
            }).id,
        })
        cls.pos_config = cls.env['pos.config'].create({
            'name': 'BI Profitability POS',
            'payment_method_ids': [Command.set(cls.pos_payment_method.ids)],
        })

    def _create_confirmed_order(self, qty, price_unit, date_order=None):
        order = self.env['sale.order'].with_company(self.profitability_company).create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
            })],
        })
        order.action_confirm()
        if date_order:
            order.date_order = date_order
        return order

    def _create_paid_pos_order(self, qty, price_unit, total_cost, date_order=None):
        if not self.pos_config.current_session_id:
            self.pos_config.open_ui()

        price_subtotal = price_unit * qty
        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.pos_config.current_session_id.id,
            'amount_total': price_subtotal,
            'amount_tax': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'lines': [Command.create({
                'product_id': self.pos_product.id,
                'qty': qty,
                'price_unit': price_unit,
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal,
                'total_cost': total_cost,
                'is_total_cost_computed': True,
            })],
        })
        payment_context = {'active_ids': order.ids, 'active_id': order.id}
        payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'payment_method_id': self.pos_payment_method.id,
            'amount': price_subtotal,
        })
        payment.with_context(**payment_context).check()
        if date_order:
            # ORM write can shift the day via timezone; set the SQL value directly.
            self.env.cr.execute(
                'UPDATE pos_order SET date_order = %s WHERE id = %s',
                [fields.Datetime.to_string(date_order), order.id],
            )
            order.invalidate_recordset(['date_order'])
        return order

    def _search_report(self, domain, company=None):
        company = company or self.profitability_company
        return self.env['bi.profitability.report'].search(
            domain + [('company_id', '=', company.id)],
        )

    def test_profitability_report_shows_daily_sales(self):
        now = fields.Datetime.now()
        sale_date = fields.Date.to_date(now)

        self._create_confirmed_order(2.0, 10.0, date_order=now)

        report = self._search_report([
            ('date', '=', sale_date),
        ])
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.sale_amount, 20.0)
        self.assertAlmostEqual(report.product_cost_amount, 8.0)
        self.assertAlmostEqual(report.gross_profit_amount, 12.0)

    def test_profitability_report_filters_by_date(self):
        now = fields.Datetime.now()
        previous_month = now - relativedelta(months=1)
        current_sale_date = fields.Date.to_date(now)
        previous_sale_date = fields.Date.to_date(previous_month)

        self._create_confirmed_order(2.0, 10.0, date_order=now)
        self._create_confirmed_order(5.0, 10.0, date_order=previous_month)

        current_report = self._search_report([
            ('date', '=', current_sale_date),
        ])
        self.assertEqual(len(current_report), 1)
        self.assertAlmostEqual(current_report.sale_amount, 20.0)

        all_reports = self._search_report([
            ('date', 'in', [current_sale_date, previous_sale_date]),
        ])
        total_sales = sum(all_reports.mapped('sale_amount'))
        self.assertAlmostEqual(total_sales, 70.0)

    def test_profitability_report_shows_all_days_in_month(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        month_end = today.replace(day=days_in_month)
        sale_day = today.replace(day=min(15, days_in_month))
        # Noon UTC avoids date shifts when PostgreSQL casts timestamp to date.
        sale_datetime = fields.Datetime.to_datetime(sale_day).replace(hour=12)

        self._create_confirmed_order(2.0, 10.0, date_order=sale_datetime)

        report = self._search_report([
            ('date', '>=', month_start),
            ('date', '<=', month_end),
        ])
        self.assertEqual(len(report), days_in_month)

        sale_rows = report.filtered(lambda r: r.sale_amount)
        self.assertEqual(len(sale_rows), 1)
        self.assertAlmostEqual(sale_rows.sale_amount, 20.0)
        self.assertAlmostEqual(sale_rows.product_cost_amount, 8.0)
        self.assertAlmostEqual(sale_rows.gross_profit_amount, 12.0)

        empty_rows = report - sale_rows
        self.assertEqual(len(empty_rows), days_in_month - 1)
        self.assertTrue(all(amount == 0.0 for amount in empty_rows.mapped('sale_amount')))
        self.assertTrue(all(amount == 0.0 for amount in empty_rows.mapped('product_cost_amount')))
        self.assertTrue(all(amount == 0.0 for amount in empty_rows.mapped('gross_profit_amount')))

    def test_profitability_report_includes_paid_pos_order(self):
        company = self.env.company
        # Isolated past date avoids mixing with other company sales of the day.
        sale_datetime = fields.Datetime.to_datetime('2019-03-15').replace(hour=12)
        sale_date = fields.Date.to_date(sale_datetime)

        order = self._create_paid_pos_order(
            2.0, 10.0, total_cost=8.0, date_order=sale_datetime,
        )
        self.assertIn(order.state, ('paid', 'done'))
        self.env.flush_all()

        report = self._search_report([('date', '=', sale_date)], company=company)
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.sale_amount, 20.0)
        self.assertAlmostEqual(report.product_cost_amount, 8.0)
        self.assertAlmostEqual(report.gross_profit_amount, 12.0)

    def test_profitability_report_uses_user_timezone_for_date(self):
        """UTC midnight+ can be the previous local day west of UTC."""
        self.env.user.tz = 'America/Mexico_City'
        # 2020-07-14 02:00 UTC == 2020-07-13 21:00 America/Mexico_City
        sale_datetime = fields.Datetime.to_datetime('2020-07-14 02:00:00')
        local_date = fields.Date.to_date('2020-07-13')
        utc_date = fields.Date.to_date('2020-07-14')

        self._create_confirmed_order(2.0, 10.0, date_order=sale_datetime)
        self.env.flush_all()

        local_report = self._search_report([('date', '=', local_date)])
        self.assertEqual(len(local_report), 1)
        self.assertAlmostEqual(local_report.sale_amount, 20.0)

        utc_report = self._search_report([('date', '=', utc_date)])
        self.assertFalse(utc_report.filtered(lambda r: r.sale_amount))
