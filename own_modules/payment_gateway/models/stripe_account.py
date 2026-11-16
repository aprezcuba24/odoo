# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PaymentGatewayStripeAccount(models.Model):
    _name = 'payment_gateway.stripe.account'
    _description = 'Cuenta Stripe por compañía'
    _order = 'company_id'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        ondelete='cascade',
        index=True,
    )
    # ACL limits who can open the model; password widget hides values in the UI.
    # No field-level groups: the public webhook reads these via sudo().
    secret_key = fields.Char(
        string='Secret key',
        copy=False,
    )
    publishable_key = fields.Char(
        string='Publishable key',
        copy=False,
    )
    webhook_secret = fields.Char(
        string='Webhook secret',
        copy=False,
    )

    _company_uniq = models.Constraint(
        'unique(company_id)',
        'Solo puede haber una cuenta Stripe por compañía.',
    )

    def has_complete_credentials(self) -> bool:
        self.ensure_one()
        return bool(
            (self.secret_key or '').strip()
            and (self.publishable_key or '').strip()
            and (self.webhook_secret or '').strip()
        )
