# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BiSupplyEntry(models.Model):
    _name = 'bi.supply.entry'
    _description = 'Entrada de insumo'
    _order = 'date desc, id desc'

    supply_id = fields.Many2one(
        'bi.supply',
        string='Insumo',
        required=True,
        ondelete='cascade',
    )
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
    )
    quantity = fields.Float(string='Cantidad', digits='Product Unit', required=True)
    unit_cost = fields.Monetary(string='Precio de costo', required=True)
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

    @api.constrains('quantity', 'unit_cost')
    def _check_positive_values(self):
        for entry in self:
            if entry.quantity <= 0:
                raise ValidationError('La cantidad debe ser mayor que cero.')
            if entry.unit_cost <= 0:
                raise ValidationError('El precio de costo debe ser mayor que cero.')

    @api.onchange('supply_id')
    def _onchange_supply_id(self):
        if self.supply_id:
            self.company_id = self.supply_id.company_id
            self.currency_id = self.supply_id.currency_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            supply = self.env['bi.supply'].browse(vals.get('supply_id'))
            if supply:
                vals.setdefault('company_id', supply.company_id.id)
                vals.setdefault('currency_id', supply.currency_id.id)
        entries = super().create(vals_list)
        entries.mapped('supply_id')._recompute_stock_metrics()
        return entries

    def write(self, vals):
        supplies = self.mapped('supply_id')
        res = super().write(vals)
        (supplies | self.mapped('supply_id'))._recompute_stock_metrics()
        return res

    def unlink(self):
        supplies = self.mapped('supply_id')
        res = super().unlink()
        supplies._recompute_stock_metrics()
        return res
