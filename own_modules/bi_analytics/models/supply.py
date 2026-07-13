# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BiSupply(models.Model):
    _name = 'bi.supply'
    _description = 'Insumo'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    unit = fields.Char(string='Unidad', required=True)
    cost = fields.Monetary(string='Costo', required=True)
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

    @api.constrains('cost')
    def _check_cost(self):
        for supply in self:
            if supply.cost <= 0:
                raise ValidationError('El costo debe ser mayor que cero.')
