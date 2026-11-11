# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

from odoo.addons.order_bridge.utils.constant import STATE_CANCELED


class OrderBridgeOrderPayment(models.Model):
    _name = 'order_bridge.order.payment'
    _description = 'Cobro de pedido (Tienda Apk)'
    _order = 'date desc, id desc'

    order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
        required=True,
        ondelete='cascade',
        index=True,
    )
    method_id = fields.Many2one(
        'order_bridge.payment.method',
        string='Vía de pago',
        required=True,
        ondelete='restrict',
        index=True,
    )
    amount = fields.Monetary(
        string='Importe',
        required=True,
        currency_field='currency_id',
    )
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related='order_id.company_id',
        store=True,
        readonly=True,
    )
    transfer_id = fields.Many2one(
        'order_bridge.transfer',
        string='Transferencia',
        ondelete='set null',
        index=True,
        copy=False,
    )

    @api.constrains('amount')
    def _check_amount_positive(self):
        for payment in self:
            if float_compare(payment.amount, 0.0, precision_rounding=payment.currency_id.rounding or 0.01) <= 0:
                raise ValidationError(_('El importe del cobro debe ser mayor que cero.'))

    @api.constrains('amount', 'order_id')
    def _check_amount_not_over_total(self):
        for order in self.mapped('order_id'):
            order._order_bridge_check_payments_not_over_total()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order = self.env['sale.order'].browse(vals.get('order_id')).exists()
            if order and order.order_bridge_store_state == STATE_CANCELED:
                raise UserError(
                    _('No se pueden añadir cobros a un pedido cancelado.')
                )
        return super().create(vals_list)

    def write(self, vals):
        if any(order.order_bridge_store_state == STATE_CANCELED for order in self.mapped('order_id')):
            raise UserError(
                _('No se pueden modificar cobros de un pedido cancelado.')
            )
        return super().write(vals)
