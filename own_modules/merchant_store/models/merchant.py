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
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        ondelete='cascade',
        index=True,
        default=lambda self: self.env.company,
    )
