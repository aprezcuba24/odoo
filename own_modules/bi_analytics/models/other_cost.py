# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BiOtherCost(models.Model):
    _name = 'bi.other.cost'
    _description = 'Otro costo'
    _order = 'date desc, id desc'

    name = fields.Char(string='Descripción', required=True)
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
    )
    amount = fields.Monetary(string='Importe', required=True)
    category_id = fields.Many2one(
        'bi.cost.category',
        string='Categoría',
        required=True,
        ondelete='restrict',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Insumo',
        domain=[('sale_ok', '=', False)],
        ondelete='restrict',
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
    notes = fields.Text(string='Notas')
    stock_scrap_id = fields.Many2one(
        'stock.scrap',
        string='Consumo de inventario',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('confirmed', 'Confirmado'),
        ],
        string='Estado',
        required=True,
        default='draft',
        readonly=True,
        copy=False,
    )

    @api.constrains('amount')
    def _check_amount(self):
        for cost in self:
            if cost.amount <= 0:
                raise ValidationError('El importe debe ser mayor que cero.')

    @api.constrains('category_id', 'product_id')
    def _check_supply_product(self):
        for cost in self:
            if cost.category_id.cost_type == 'supply' and not cost.product_id:
                raise ValidationError(
                    'Los gastos de tipo insumo deben estar vinculados a un producto insumo.',
                )
            if cost.category_id.cost_type != 'supply' and cost.product_id:
                raise ValidationError(
                    'Solo los gastos de tipo insumo pueden vincularse a un producto.',
                )

    def action_confirm(self):
        for cost in self:
            if cost.state != 'draft':
                raise UserError('Solo se pueden confirmar gastos en borrador.')
        self.write({'state': 'confirmed'})

    def action_draft(self):
        for cost in self:
            if cost.state != 'confirmed':
                raise UserError('Solo se pueden devolver a borrador los gastos confirmados.')
        self.write({'state': 'draft'})
