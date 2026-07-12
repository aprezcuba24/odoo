# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class BiCostCategory(models.Model):
    _name = 'bi.cost.category'
    _description = 'Categoría de costo'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    cost_type = fields.Selection(
        selection=[
            ('fixed', 'Costo fijo'),
            ('supply', 'Insumo'),
            ('other', 'Otro'),
        ],
        string='Tipo de costo',
        required=True,
        default='other',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
