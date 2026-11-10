# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class OrderBridgePaymentMethod(models.Model):
    _name = 'order_bridge.payment.method'
    _description = 'Vía de pago (Tienda Apk)'
    _order = 'sequence, name, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        'unique(name)',
        'Ya existe una vía de pago con ese nombre.',
    )
