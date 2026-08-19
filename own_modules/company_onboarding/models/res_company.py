# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, api, models

ONBOARDING_DEFAULT_LANG = 'es_ES'


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _company_onboarding_lang_code(self):
        """Return ONBOARDING_DEFAULT_LANG if active, else False."""
        return self.env['res.lang']._get_code(ONBOARDING_DEFAULT_LANG)

    @api.model
    def _company_onboarding_set_default_lang(self):
        """Called from data XML to set es_ES as default partner language."""
        lang_code = self._company_onboarding_lang_code()
        if lang_code:
            self.env['ir.default'].sudo().set('res.partner', 'lang', lang_code)

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        self._company_onboarding_unlink_system_users(companies)
        lang_code = self._company_onboarding_lang_code()
        for company in companies:
            partner = company.partner_id
            vals = {}
            if partner and partner.company_id != company:
                vals['company_id'] = company.id
            if lang_code and partner and partner.lang != lang_code:
                vals['lang'] = lang_code
            if vals and partner:
                partner.sudo().write(vals)
        return companies

    def _company_onboarding_unlink_system_users(self, companies):
        """Keep new tenant companies off Settings admins; OdooBot may keep them."""
        root = self.env.ref('base.user_root', raise_if_not_found=False)
        system_group = self.env.ref('base.group_system', raise_if_not_found=False)
        if not companies or not system_group:
            return
        to_unlink = system_group.sudo().user_ids
        if root:
            to_unlink -= root
        if not to_unlink:
            return
        for company in companies:
            holders = to_unlink.filtered(lambda u, cid=company.id: cid in u.company_ids.ids)
            if holders:
                holders.sudo().write({'company_ids': [Command.unlink(company.id)]})

    def _order_bridge_product_domain(self):
        """Catálogo Tienda Apk: solo productos de esta compañía (sin compartidos)."""
        self.ensure_one()
        return [
            ('sale_ok', '=', True),
            ('active', '=', True),
            ('product_tmpl_id.order_bridge_visible', '=', True),
            ('product_tmpl_id.company_id', '=', self.id),
        ]
