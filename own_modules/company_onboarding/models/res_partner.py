# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        # res.company.create builds the company partner first with
        # default_parent_id=False; stamping env.company there makes stock
        # warehouse _check_company fail (partner still belongs to main).
        stamp_company = self.env.context.get('default_parent_id') is not False
        for vals in vals_list:
            if stamp_company and not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
        return super().create(vals_list)
