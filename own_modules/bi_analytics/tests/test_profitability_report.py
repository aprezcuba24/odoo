# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_is_zero


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
        cls.storable_product = cls.env['product.product'].with_company(cls.profitability_company).create({
            'name': 'BI Profitability Storable Product',
            'sale_ok': True,
            'is_storable': True,
            'list_price': 10.0,
            'standard_price': 4.0,
        })
        wh = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.profitability_company.id)], limit=1,
        )
        cls.env['stock.quant'].with_company(cls.profitability_company).with_context(
            inventory_mode=True,
        ).create({
            'product_id': cls.storable_product.id,
            'location_id': wh.lot_stock_id.id,
            'inventory_quantity': 50.0,
        }).action_apply_inventory()
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
        cls.fixed_category = cls.env.ref('bi_analytics.cost_category_fixed')

    def _create_confirmed_order(self, qty, price_unit, date_order=None, product=None):
        product = product or self.product
        order = self.env['sale.order'].with_company(self.profitability_company).create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
            })],
        })
        order.action_confirm()
        if date_order:
            order.date_order = date_order
        return order

    def _validate_outgoing_picking(self, order):
        picking = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing' and p.state != 'done',
        )[:1]
        self.assertTrue(picking)
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()
        return picking

    def _return_picking(self, picking, qty):
        return_wiz = self.env['stock.return.picking'].with_context(
            active_id=picking.id,
            active_model='stock.picking',
        ).create({})
        for ret_line in return_wiz.product_return_moves:
            ret_line.quantity = qty
        res = return_wiz.action_create_returns()
        return_picking = self.env['stock.picking'].browse(res['res_id'])
        return_picking.action_confirm()
        return_picking.action_assign()
        for move in return_picking.move_ids:
            mlines = move.move_line_ids
            if mlines:
                mlines.quantity = move.product_uom_qty
            move.picked = True
        return_picking.button_validate()
        return return_picking

    def _create_paid_pos_order(self, qty, price_unit, total_cost, date_order=None, price_subtotal=None):
        if not self.pos_config.current_session_id:
            self.pos_config.open_ui()

        # POS refund lines keep a positive subtotal with negative qty.
        if price_subtotal is None:
            price_subtotal = abs(price_unit * qty) if qty < 0 else price_unit * qty
        payment_amount = -price_subtotal if qty < 0 else price_subtotal
        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.pos_config.current_session_id.id,
            'amount_total': payment_amount,
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
            'amount': payment_amount,
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

    def _create_other_cost(self, amount, date, state='confirmed', company=None):
        company = company or self.profitability_company
        cost = self.env['bi.other.cost'].create({
            'name': 'BI Profitability Fixed Cost',
            'date': date,
            'amount': amount,
            'category_id': self.fixed_category.id,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
        })
        if state == 'confirmed':
            cost.action_confirm()
        return cost

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
        self.assertAlmostEqual(report.other_cost_amount, 0.0)
        self.assertAlmostEqual(report.total_cost_amount, 8.0)
        self.assertAlmostEqual(report.profit_amount, 12.0)

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

    def test_profitability_report_signs_pos_refund_line(self):
        """POS refunds store negative qty and positive price_subtotal."""
        company = self.env.company
        sale_datetime = fields.Datetime.to_datetime('2019-04-20').replace(hour=12)
        sale_date = fields.Date.to_date(sale_datetime)

        order = self._create_paid_pos_order(
            -1.0, 10.0, total_cost=-4.0, date_order=sale_datetime, price_subtotal=10.0,
        )
        self.assertIn(order.state, ('paid', 'done'))
        self.assertEqual(order.lines.qty, -1.0)
        self.assertAlmostEqual(order.lines.price_subtotal, 10.0)
        self.env.flush_all()

        report = self._search_report([('date', '=', sale_date)], company=company)
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.sale_amount, -10.0)
        self.assertAlmostEqual(report.product_cost_amount, -4.0)
        self.assertAlmostEqual(report.gross_profit_amount, -6.0)

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

    def test_profitability_report_includes_confirmed_other_cost(self):
        sale_day = fields.Date.to_date('2018-06-10')
        sale_datetime = fields.Datetime.to_datetime(sale_day).replace(hour=12)

        self._create_confirmed_order(10.0, 10.0, date_order=sale_datetime)
        self._create_other_cost(10.0, sale_day)
        self.env.flush_all()

        report = self._search_report([('date', '=', sale_day)])
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.sale_amount, 100.0)
        self.assertAlmostEqual(report.product_cost_amount, 40.0)
        self.assertAlmostEqual(report.gross_profit_amount, 60.0)
        self.assertAlmostEqual(report.other_cost_amount, 10.0)
        self.assertAlmostEqual(report.total_cost_amount, 50.0)
        self.assertAlmostEqual(report.profit_amount, 50.0)

    def test_profitability_report_excludes_draft_other_cost(self):
        sale_day = fields.Date.to_date('2018-07-10')
        sale_datetime = fields.Datetime.to_datetime(sale_day).replace(hour=12)

        self._create_confirmed_order(2.0, 10.0, date_order=sale_datetime)
        self._create_other_cost(25.0, sale_day, state='draft')
        self.env.flush_all()

        report = self._search_report([('date', '=', sale_day)])
        self.assertEqual(len(report), 1)
        self.assertAlmostEqual(report.other_cost_amount, 0.0)
        self.assertAlmostEqual(report.total_cost_amount, 8.0)
        self.assertAlmostEqual(report.profit_amount, 12.0)

    def test_profitability_summary_computes_global_kpis(self):
        sale_day = fields.Date.to_date('2018-08-15')
        sale_datetime = fields.Datetime.to_datetime(sale_day).replace(hour=12)

        self._create_confirmed_order(10.0, 10.0, date_order=sale_datetime)
        self._create_other_cost(10.0, sale_day)
        self.env.flush_all()

        summary = self.env['bi.profitability.summary'].create({
            'date_from': sale_day,
            'date_to': sale_day,
            'company_id': self.profitability_company.id,
        })
        summary._reload_data()

        self.assertAlmostEqual(summary.sale_amount, 100.0)
        self.assertAlmostEqual(summary.product_cost_amount, 40.0)
        self.assertAlmostEqual(summary.other_cost_amount, 10.0)
        self.assertAlmostEqual(summary.total_cost_amount, 50.0)
        self.assertAlmostEqual(summary.cost_per_sale_pct, 40.0)
        self.assertAlmostEqual(summary.total_cost_index_pct, 50.0)
        self.assertAlmostEqual(summary.profit_pct, 50.0)
        self.assertAlmostEqual(summary.profit_amount, 50.0)
        self.assertEqual(len(summary.line_ids), 1)
        self.assertAlmostEqual(summary.line_ids.sale_amount, 100.0)

    def test_profitability_summary_action_open(self):
        action = self.env['bi.profitability.summary'].action_open()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'bi.profitability.summary')
        self.assertTrue(action['res_id'])
        summary = self.env['bi.profitability.summary'].browse(action['res_id'])
        self.assertTrue(summary.date_from)
        self.assertTrue(summary.date_to)

    def test_profitability_summary_month_navigation(self):
        summary = self.env['bi.profitability.summary'].create({
            'date_from': fields.Date.to_date('2018-08-01'),
            'date_to': fields.Date.to_date('2018-08-31'),
            'company_id': self.profitability_company.id,
        })
        summary.action_previous_month()
        self.assertEqual(summary.date_from, fields.Date.to_date('2018-07-01'))
        self.assertEqual(summary.date_to, fields.Date.to_date('2018-07-31'))
        summary.action_next_month()
        self.assertEqual(summary.date_from, fields.Date.to_date('2018-08-01'))
        self.assertEqual(summary.date_to, fields.Date.to_date('2018-08-31'))

    def test_profitability_report_excludes_full_delivery_return(self):
        """Fully returned deliveries must not count toward daily sales."""
        sale_day = fields.Date.to_date('2018-09-12')
        sale_datetime = fields.Datetime.to_datetime(sale_day).replace(hour=12)

        order = self._create_confirmed_order(
            2.0, 10.0, date_order=sale_datetime, product=self.storable_product,
        )
        picking = self._validate_outgoing_picking(order)
        line = order.order_line
        self.assertAlmostEqual(line.qty_delivered, 2.0)
        self.env.flush_all()

        report_before = self._search_report([('date', '=', sale_day)])
        self.assertEqual(len(report_before), 1)
        self.assertAlmostEqual(report_before.sale_amount, 20.0)

        self._return_picking(picking, 2.0)
        self.assertTrue(
            float_is_zero(line.qty_delivered, precision_rounding=line.product_uom_id.rounding),
        )
        self.env.flush_all()
        # Report row ids are deterministic (company + date); clear cache so the
        # post-return search does not reuse the pre-return sale_amount.
        self.env.invalidate_all()

        report_after = self._search_report([('date', '=', sale_day)])
        self.assertTrue(report_after)
        self.assertAlmostEqual(report_after.sale_amount, 0.0)
        self.assertAlmostEqual(report_after.product_cost_amount, 0.0)
        self.assertAlmostEqual(report_after.gross_profit_amount, 0.0)
