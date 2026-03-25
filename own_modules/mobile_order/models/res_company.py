# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    mobile_pos_config_id = fields.Many2one(
        'pos.config',
        string='Mobile app point of sale',
        help='Products and categories exposed by the mobile API match this point of sale configuration.',
        check_company=True,
    )

    @api.constrains('mobile_pos_config_id')
    def _check_mobile_pos_config_company(self):
        for company in self:
            cfg = company.mobile_pos_config_id
            if cfg and cfg.company_id != company:
                raise ValidationError(
                    _('The mobile point of sale must belong to the same company (%s).')
                    % company.display_name
                )

    @api.model
    def _mobile_order_catalog_company_for_partner(self, partner, env_company):
        """Company whose linked POS config applies (partner company or current env company)."""
        partner = partner.sudo()
        return partner.company_id or env_company

    def _mobile_order_pos_config(self):
        self.ensure_one()
        return self.mobile_pos_config_id

    def _mobile_order_product_domain(self):
        """Domain on product.product matching the linked POS (same rules as POS data load)."""
        self.ensure_one()
        config = self.mobile_pos_config_id
        if not config:
            return [('id', '=', False)]
        Template = self.env['product.template'].sudo()
        tmpl_domain = Template._load_pos_data_domain({}, config)
        template_ids = Template.search(tmpl_domain).ids
        if not template_ids:
            return [('id', '=', False)]
        return [('product_tmpl_id', 'in', template_ids), ('active', '=', True)]
