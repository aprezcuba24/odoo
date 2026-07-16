# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.fields import Command


class BiProfitabilitySummary(models.TransientModel):
    _name = 'bi.profitability.summary'
    _description = 'IPV'
    _rec_name = 'date_from'

    date_from = fields.Date(string='Periodo', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
    )
    line_ids = fields.One2many(
        'bi.profitability.summary.line',
        'summary_id',
        string='Detalle diario',
    )
    sale_amount = fields.Monetary(string='Ventas', readonly=True)
    product_cost_amount = fields.Monetary(string='Costo de productos', readonly=True)
    other_cost_amount = fields.Monetary(string='Otros costos', readonly=True)
    total_cost_amount = fields.Monetary(string='Costo total', readonly=True)
    cost_per_sale_pct = fields.Float(
        string='Costo por peso de venta (%)',
        readonly=True,
        digits=(16, 2),
    )
    total_cost_index_pct = fields.Float(
        string='Índice de costo total (%)',
        readonly=True,
        digits=(16, 2),
    )
    profit_pct = fields.Float(
        string='% ganancia',
        readonly=True,
        digits=(16, 2),
    )
    profit_amount = fields.Monetary(string='Utilidad en valor', readonly=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        defaults.setdefault('date_from', month_start)
        defaults.setdefault('date_to', month_end)
        defaults.setdefault('company_id', self.env.company.id)
        return defaults

    @api.model
    def action_open(self):
        summary = self.create({})
        summary._reload_data()
        return {
            'name': _('IPV'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': summary.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    @api.onchange('date_from', 'date_to', 'company_id')
    def _onchange_filters(self):
        self._reload_data()

    def action_previous_month(self):
        self.ensure_one()
        self._set_month_offset(-1)
        return True

    def action_next_month(self):
        self.ensure_one()
        self._set_month_offset(1)
        return True

    def _set_month_offset(self, months):
        base = self.date_from or fields.Date.context_today(self)
        month_start = base.replace(day=1) + relativedelta(months=months)
        month_end = month_start + relativedelta(months=1, days=-1)
        self.write({
            'date_from': month_start,
            'date_to': month_end,
        })
        self._reload_data()

    def _reload_data(self):
        for summary in self:
            if not summary.date_from or not summary.date_to or not summary.company_id:
                summary.line_ids = [Command.clear()]
                summary.sale_amount = 0.0
                summary.product_cost_amount = 0.0
                summary.other_cost_amount = 0.0
                summary.total_cost_amount = 0.0
                summary.cost_per_sale_pct = 0.0
                summary.total_cost_index_pct = 0.0
                summary.profit_pct = 0.0
                summary.profit_amount = 0.0
                continue

            reports = self.env['bi.profitability.report'].search([
                ('company_id', '=', summary.company_id.id),
                ('date', '>=', summary.date_from),
                ('date', '<=', summary.date_to),
            ], order='date asc')

            summary.line_ids = [Command.clear()] + [
                Command.create({
                    'date': row.date,
                    'sale_amount': row.sale_amount,
                    'product_cost_amount': row.product_cost_amount,
                    'gross_profit_amount': row.gross_profit_amount,
                    'currency_id': row.currency_id.id,
                })
                for row in reports
            ]

            sale_amount = sum(reports.mapped('sale_amount'))
            product_cost_amount = sum(reports.mapped('product_cost_amount'))
            other_cost_amount = sum(reports.mapped('other_cost_amount'))
            total_cost_amount = product_cost_amount + other_cost_amount

            summary.sale_amount = sale_amount
            summary.product_cost_amount = product_cost_amount
            summary.other_cost_amount = other_cost_amount
            summary.total_cost_amount = total_cost_amount
            summary.profit_amount = sale_amount - total_cost_amount
            if sale_amount:
                summary.cost_per_sale_pct = product_cost_amount / sale_amount * 100.0
                summary.total_cost_index_pct = total_cost_amount / sale_amount * 100.0
                summary.profit_pct = 100.0 - summary.total_cost_index_pct
            else:
                summary.cost_per_sale_pct = 0.0
                summary.total_cost_index_pct = 0.0
                summary.profit_pct = 0.0


class BiProfitabilitySummaryLine(models.TransientModel):
    _name = 'bi.profitability.summary.line'
    _description = 'Línea de resumen de rentabilidad'
    _order = 'date asc'

    summary_id = fields.Many2one(
        'bi.profitability.summary',
        string='Resumen',
        required=True,
        ondelete='cascade',
    )
    date = fields.Date(string='Fecha', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    sale_amount = fields.Monetary(string='Ventas', readonly=True)
    product_cost_amount = fields.Monetary(string='Costo de productos', readonly=True)
    gross_profit_amount = fields.Monetary(string='Margen bruto', readonly=True)
