# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import AccessError


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

    def check_access(self, operation):
        """System admins may touch commercial partners of companies they manage.

        Tenant company partners get ``company_id`` = that company. After
        onboarding unlinks Settings admins from the tenant, the global partner
        rule blocks those partners and the company form / Entrar save fails
        with AccessError. Allow system users through for company entity partners
        only (not every contact).
        """
        try:
            return super().check_access(operation)
        except AccessError:
            if self.env.su or not self.env.user.has_group('base.group_system'):
                raise
            if not self:
                raise
            company_partners = self.env['res.company'].sudo().search([]).partner_id
            if self <= company_partners:
                return
            raise
