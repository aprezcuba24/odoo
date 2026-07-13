# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


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
    amount = fields.Monetary(
        string='Importe',
        compute='_compute_amount',
        store=True,
        readonly=False,
    )
    category_id = fields.Many2one(
        'bi.cost.category',
        string='Categoría',
        required=True,
        ondelete='restrict',
    )
    cost_type = fields.Selection(related='category_id.cost_type')
    supply_id = fields.Many2one(
        'bi.supply',
        string='Insumo',
        ondelete='restrict',
    )
    quantity = fields.Float(string='Cantidad', digits='Product Unit')
    unit_cost = fields.Monetary(string='Precio unitario', readonly=True)
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

    @api.onchange('supply_id', 'quantity', 'category_id')
    def _onchange_supply_description(self):
        if self.cost_type == 'supply' and self.supply_id:
            self.name = self._supply_description(self.supply_id, self.quantity)
            self.unit_cost = self.supply_id.average_cost

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_supply_description(vals)
            self._apply_supply_unit_cost(vals)
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if {'supply_id', 'quantity', 'category_id'} & set(vals):
            for cost in self.filtered(lambda c: c.cost_type == 'supply' and c.state == 'draft'):
                cost.name = cost._supply_description(cost.supply_id, cost.quantity)
                cost.unit_cost = cost.supply_id.average_cost
        return res

    def _supply_description(self, supply, quantity):
        supply = supply or self.env['bi.supply']
        qty = quantity or 0.0
        if not supply:
            return False
        return f'{supply.name} ({qty:g} {supply.unit})'

    def _apply_supply_description(self, vals):
        if vals.get('name'):
            return
        category = self.env['bi.cost.category'].browse(vals.get('category_id'))
        if category.cost_type != 'supply':
            return
        supply = self.env['bi.supply'].browse(vals.get('supply_id'))
        description = self._supply_description(supply, vals.get('quantity', 0.0))
        if description:
            vals['name'] = description

    def _apply_supply_unit_cost(self, vals):
        category = self.env['bi.cost.category'].browse(vals.get('category_id'))
        if category.cost_type != 'supply':
            return
        supply = self.env['bi.supply'].browse(vals.get('supply_id'))
        if supply:
            vals['unit_cost'] = supply.average_cost

    @api.constrains('category_id', 'name')
    def _check_name(self):
        for cost in self:
            if cost.cost_type != 'supply' and not cost.name:
                raise ValidationError('La descripción es obligatoria.')

    @api.depends('category_id.cost_type', 'unit_cost', 'quantity')
    def _compute_amount(self):
        for cost in self:
            if cost.category_id.cost_type == 'supply':
                cost.amount = (cost.unit_cost or 0.0) * (cost.quantity or 0.0)

    @api.constrains('category_id', 'amount')
    def _check_amount(self):
        for cost in self:
            if cost.category_id.cost_type != 'supply' and cost.amount <= 0:
                raise ValidationError('El importe debe ser mayor que cero.')

    @api.constrains('category_id', 'supply_id', 'quantity')
    def _check_supply(self):
        for cost in self:
            if cost.category_id.cost_type == 'supply':
                if not cost.supply_id:
                    raise ValidationError(
                        'Los gastos de tipo insumo deben estar vinculados a un insumo.',
                    )
                if cost.quantity <= 0:
                    raise ValidationError('La cantidad debe ser mayor que cero.')
                if cost.amount <= 0:
                    raise ValidationError('El importe debe ser mayor que cero.')
            else:
                if cost.supply_id:
                    raise ValidationError(
                        'Solo los gastos de tipo insumo pueden vincularse a un insumo.',
                    )
                if cost.quantity:
                    raise ValidationError(
                        'Solo los gastos de tipo insumo pueden tener cantidad.',
                    )

    def _check_supply_stock(self):
        for cost in self.filtered(lambda c: c.cost_type == 'supply'):
            available = cost.supply_id.qty_available
            if float_compare(
                available,
                cost.quantity,
                precision_digits=6,
            ) < 0:
                raise ValidationError(
                    f'No hay stock suficiente de {cost.supply_id.name}. '
                    f'Disponible: {available:g} {cost.supply_id.unit}.',
                )

    def action_confirm(self):
        for cost in self:
            if cost.state != 'draft':
                raise UserError('Solo se pueden confirmar gastos en borrador.')
        supply_costs = self.filtered(lambda c: c.cost_type == 'supply')
        supply_costs._check_supply_stock()
        for cost in supply_costs:
            cost.write({
                'unit_cost': cost.supply_id.average_cost,
                'state': 'confirmed',
            })
        (self - supply_costs).write({'state': 'confirmed'})
        supply_costs.mapped('supply_id')._recompute_stock_metrics()

    def action_draft(self):
        supply_costs = self.filtered(lambda c: c.cost_type == 'supply')
        for cost in self:
            if cost.state != 'confirmed':
                raise UserError('Solo se pueden devolver a borrador los gastos confirmados.')
        self.write({'state': 'draft'})
        for cost in supply_costs:
            cost.unit_cost = cost.supply_id.average_cost
        supply_costs.mapped('supply_id')._recompute_stock_metrics()
