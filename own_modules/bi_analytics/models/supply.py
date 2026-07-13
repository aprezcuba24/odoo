# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_is_zero


class BiSupply(models.Model):
    _name = 'bi.supply'
    _description = 'Insumo'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    unit = fields.Char(string='Unidad', required=True)
    average_cost = fields.Monetary(
        string='Costo promedio',
        readonly=True,
        default=0.0,
    )
    qty_available = fields.Float(
        string='Stock disponible',
        digits='Product Unit',
        readonly=True,
        default=0.0,
    )
    entry_ids = fields.One2many(
        'bi.supply.entry',
        'supply_id',
        string='Entradas',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'bi_supply' AND column_name IN ('cost', 'average_cost')
            """,
        )
        columns = {row[0] for row in self.env.cr.fetchall()}
        if 'cost' in columns and 'average_cost' not in columns:
            self.env.cr.execute(
                """
                ALTER TABLE bi_supply RENAME COLUMN cost TO average_cost
                """,
            )
        elif 'cost' in columns and 'average_cost' in columns:
            self.env.cr.execute(
                """
                UPDATE bi_supply
                SET average_cost = cost
                WHERE cost IS NOT NULL AND (average_cost IS NULL OR average_cost = 0)
                """,
            )
            self.env.cr.execute(
                """
                ALTER TABLE bi_supply DROP COLUMN cost
                """,
            )

    def _recompute_stock_metrics(self):
        supply_category = self.env.ref(
            'bi_analytics.cost_category_supply',
            raise_if_not_found=False,
        )
        for supply in self:
            qty = 0.0
            avg_cost = 0.0
            events = []

            for entry in supply.entry_ids.sorted(lambda e: (e.date, e.id)):
                events.append(('in', entry.date, entry.id, entry.quantity, entry.unit_cost))

            if supply_category:
                costs = self.env['bi.other.cost'].search([
                    ('supply_id', '=', supply.id),
                    ('category_id', '=', supply_category.id),
                    ('state', '=', 'confirmed'),
                ])
                for cost in costs.sorted(lambda c: (c.date, c.id)):
                    events.append(('out', cost.date, cost.id, cost.quantity, 0.0))

            events.sort(key=lambda event: (event[1], 0 if event[0] == 'in' else 1, event[2]))

            for event_type, _date, _id, quantity, unit_cost in events:
                if event_type == 'in':
                    if float_is_zero(qty, precision_digits=6):
                        avg_cost = unit_cost
                    else:
                        avg_cost = ((qty * avg_cost) + (quantity * unit_cost)) / (qty + quantity)
                    qty += quantity
                else:
                    qty -= quantity

            supply.write({
                'qty_available': qty,
                'average_cost': avg_cost,
            })
