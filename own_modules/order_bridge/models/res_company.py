# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _order_bridge_catalog_company_for_partner(self, partner, env_company):
        """Empresa usada para el dominio del catálogo (empresa del contacto o empresa actual)."""
        if not partner:
            return env_company
        partner = partner.sudo()
        return partner.company_id or env_company

    def _order_bridge_product_domain(self):
        """Dominio en product.product para el catálogo Tienda Apk."""
        self.ensure_one()
        company = self
        return [
            ('sale_ok', '=', True),
            ('active', '=', True),
            ('product_tmpl_id.order_bridge_visible', '=', True),
            '|',
            ('product_tmpl_id.company_id', '=', False),
            ('product_tmpl_id.company_id', '=', company.id),
        ]
