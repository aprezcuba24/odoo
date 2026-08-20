# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_SLUG_RE = re.compile(r'^[a-z][a-z0-9-]{1,62}$')

TENANT_GROUP_XMLIDS = (
    'base.group_user',
    'sales_team.group_sale_manager',
    'stock.group_stock_manager',
    'point_of_sale.group_pos_manager',
    'product.group_product_manager',
    'account.group_account_invoice',
    'order_bridge.group_order_bridge_manager',
)


class CompanyOnboardingWizard(models.TransientModel):
    _name = 'company.onboarding.wizard'
    _description = 'Asistente: crear mi compañía'

    company_name = fields.Char(string='Nombre de la empresa', required=True)
    order_bridge_slug = fields.Char(
        string='Slug Tienda Apk',
        required=True,
        help='Identificador público (subdominio / X-Company-Slug). Solo minúsculas, números y guiones.',
    )
    country_id = fields.Many2one(
        'res.country',
        string='País',
        required=True,
        default=lambda self: self.env.company.country_id,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    phone = fields.Char(string='Teléfono de la tienda')

    @api.constrains('order_bridge_slug')
    def _check_slug(self):
        for wiz in self:
            slug = (wiz.order_bridge_slug or '').strip().lower()
            if not _SLUG_RE.match(slug):
                raise ValidationError(
                    _(
                        'El slug debe empezar por letra minúscula y solo contener '
                        'letras minúsculas, números y guiones (2–63 caracteres).'
                    ),
                )

    def action_create_company(self):
        self.ensure_one()
        user = self.env.user
        if not user._is_company_onboarding_pending():
            raise UserError(_('El onboarding de compañía ya está completado.'))
        if user.has_group('base.group_system'):
            raise AccessError(_('Los administradores de sistema no usan este asistente.'))

        slug = self.order_bridge_slug.strip().lower()
        Company = self.env['res.company'].sudo()
        if Company.search_count([('order_bridge_slug', '=', slug)]):
            raise UserError(_('Ese slug ya está en uso. Elige otro.'))

        company = Company.create({
            'name': self.company_name.strip(),
            'country_id': self.country_id.id,
            'currency_id': self.currency_id.id,
            'order_bridge_slug': slug,
            'phone': self.phone or False,
        })

        self._ensure_chart_of_accounts(company)
        self._ensure_pos_config(company)

        group_ids = self._default_tenant_group_ids()
        user.sudo().write({
            'company_ids': [Command.set([company.id])],
            'company_id': company.id,
            'group_ids': [Command.set(group_ids)],
            'company_onboarding_state': 'done',
            'action_id': False,
        })

        if self.phone:
            Settings = self.env['order_bridge.general_settings'].sudo()
            settings = Settings._get_or_create_for_company(company)
            settings.write({'shop_phone': self.phone})

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _default_tenant_group_ids(self):
        """Grupos de operación para el admin de la nueva compañía (sin system / multi-company)."""
        groups = self.env['res.groups']
        for xid in TENANT_GROUP_XMLIDS:
            group = self.env.ref(xid, raise_if_not_found=False)
            if group:
                groups |= group
        return groups.ids

    @api.model
    def _chart_template_code_for_country(self, country):
        """Template whose module is already installed; never trigger a module install."""
        ChartTemplate = self.env['account.chart.template'].sudo()
        guessed = ChartTemplate._guess_chart_template(country)
        mapping = ChartTemplate._get_chart_template_mapping()
        info = mapping.get(guessed) or {}
        module_name = info.get('module') or 'account'
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', module_name)],
            limit=1,
        )
        if module.state == 'installed':
            return guessed
        return 'generic_coa'

    @api.model
    def _ensure_chart_of_accounts(self, company):
        """Load a CoA without installing l10n modules; keep the chosen currency and country."""
        company = company.sudo()
        currency = company.currency_id
        country = company.country_id
        if not company.chart_template:
            template_code = self._chart_template_code_for_country(country)
            self.env['account.chart.template'].sudo().with_company(company).with_context(
                allowed_company_ids=[company.id],
            ).try_loading(template_code, company, install_demo=False)
            company.invalidate_recordset()
        vals = {}
        if currency and company.currency_id != currency:
            vals['currency_id'] = currency.id
        if country and company.account_fiscal_country_id != country:
            vals['account_fiscal_country_id'] = country.id
        if vals:
            company.write(vals)

    @api.model
    def _ensure_pos_config(self, company):
        """Create a retail PoS (no demo) so the dashboard is not blocked by scenario cards."""
        PosConfig = self.env['pos.config'].sudo().with_company(company).with_context(
            allowed_company_ids=[company.id],
        )
        if PosConfig.search_count([('company_id', '=', company.id)]):
            return
        PosConfig.load_onboarding_retail_scenario(False)
