# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MerchantStoreMerchant(models.Model):
    _name = 'merchant_store.merchant'
    _description = 'Comerciante externo'
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    description = fields.Text(string='Descripción')
    logo = fields.Image(string='Logo')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        ondelete='cascade',
        index=True,
        default=lambda self: self.env.company,
    )

    def _can_return_content(self, field_name=None, access_token=None):
        """Allow public ``/web/image`` for logos of active merchants (same company)."""
        if field_name not in ('logo', 'logo_128', 'logo_256', 'logo_512'):
            return super()._can_return_content(field_name, access_token)
        self.ensure_one()
        rec = self.sudo()
        if not rec.active or not rec.logo:
            return False
        if rec.company_id != self.env.company:
            return False
        return True
