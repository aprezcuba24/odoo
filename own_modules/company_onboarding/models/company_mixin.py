# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class CompanyOnboardingCompanyMixin(models.AbstractModel):
    _name = 'company.onboarding.company.mixin'
    _description = 'Asignar company_id a env.company si falta'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
        return super().create(vals_list)
