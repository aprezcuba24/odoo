# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class OrderBridgeGeneralSettings(models.Model):
    _name = 'order_bridge.general_settings'
    _description = 'Datos generales Tienda Apk'
    _order = 'company_id'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        ondelete='cascade',
        index=True,
    )
    shop_phone = fields.Char(string='Teléfono de la tienda')

    _sql_constraints = [
        (
            'company_uniq',
            'unique(company_id)',
            'Solo puede haber una configuración general por compañía.',
        ),
    ]

    @api.model
    def _ensure_rows_for_all_companies(self):
        """Crea un registro por compañía si falta (p. ej. al actualizar el módulo)."""
        Company = self.env['res.company'].sudo()
        companies = Company.search([])
        for company in companies:
            self._get_or_create_for_company(company)

    @api.model
    def _get_or_create_for_company(self, company):
        company = company.sudo()
        existing = self.search([('company_id', '=', company.id)], limit=1)
        if existing:
            return existing
        return self.create({'company_id': company.id})
