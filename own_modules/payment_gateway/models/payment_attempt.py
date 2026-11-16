# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PaymentGatewayPaymentAttempt(models.Model):
    _name = 'payment_gateway.payment.attempt'
    _description = 'Intento de cobro online'
    _order = 'id desc'

    order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
        required=True,
        ondelete='cascade',
        index=True,
    )
    provider_code = fields.Char(
        string='Proveedor',
        required=True,
        index=True,
    )
    external_id = fields.Char(
        string='Id externo',
        required=True,
        index=True,
    )
    client_secret = fields.Char(
        string='Client secret',
        groups='base.group_system',
        copy=False,
    )
    state = fields.Selection(
        selection=[
            ('open', 'Abierto'),
            ('succeeded', 'Confirmado'),
            ('failed', 'Fallido'),
            ('canceled', 'Cancelado'),
        ],
        string='Estado',
        required=True,
        default='open',
        index=True,
    )
    amount = fields.Monetary(
        string='Importe',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
    )
    company_id = fields.Many2one(
        related='order_id.company_id',
        store=True,
        readonly=True,
    )

    _external_id_unique = models.Constraint(
        'unique(external_id)',
        'Ya existe un intento con ese identificador externo.',
    )
