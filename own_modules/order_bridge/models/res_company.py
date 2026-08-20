# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_SLUG_RE = re.compile(r'^[a-z][a-z0-9-]{1,62}$')


class ResCompany(models.Model):
    _inherit = 'res.company'

    order_bridge_slug = fields.Char(
        string='Slug Tienda Apk',
        help=(
            'Identificador público de la tienda en la API móvil '
            '(header X-Company-Slug, body company_slug o subdominio). '
            'Minúsculas, números y guiones; único.'
        ),
        index=True,
        copy=False,
    )

    _order_bridge_slug_uniq = models.Constraint(
        'unique(order_bridge_slug)',
        'El slug Tienda Apk debe ser único.',
    )

    @api.constrains('order_bridge_slug')
    def _check_order_bridge_slug(self):
        for company in self:
            slug = (company.order_bridge_slug or '').strip()
            if not slug:
                continue
            if not _SLUG_RE.match(slug):
                raise ValidationError(
                    _(
                        'El slug Tienda Apk debe empezar por letra minúscula y '
                        'solo contener letras minúsculas, números y guiones '
                        '(2–63 caracteres).'
                    ),
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_bridge_slug'):
                vals['order_bridge_slug'] = vals['order_bridge_slug'].strip().lower()
        companies = super().create(vals_list)
        GeneralSettings = self.env['order_bridge.general_settings'].sudo()
        Sequence = self.env['ir.sequence'].sudo()
        for company in companies:
            GeneralSettings._get_or_create_for_company(company)
            if not Sequence.search_count([
                ('code', '=', 'order_bridge.order.ref'),
                ('company_id', '=', company.id),
            ]):
                Sequence.create({
                    'name': f'Referencia Tienda Apk ({company.name})',
                    'code': 'order_bridge.order.ref',
                    'prefix': 'OB-',
                    'padding': 5,
                    'company_id': company.id,
                })
        return companies

    def write(self, vals):
        if 'order_bridge_slug' in vals:
            vals = dict(vals)
            slug = vals.get('order_bridge_slug')
            if slug is not None and not str(slug).strip():
                vals['order_bridge_slug'] = False
            elif slug:
                vals['order_bridge_slug'] = str(slug).strip().lower()
        return super().write(vals)

    @api.model
    def _order_bridge_catalog_company_for_partner(self, partner, env_company):
        """Empresa usada para el dominio del catálogo (empresa del contacto o empresa actual)."""
        if not partner:
            return env_company
        partner = partner.sudo()
        return partner.company_id or env_company

    @api.model
    def _order_bridge_find_by_slug(self, slug):
        """Return company for a public Tienda Apk slug, or empty recordset."""
        slug = (slug or '').strip().lower()
        if not slug:
            return self.browse()
        return self.sudo().search([('order_bridge_slug', '=', slug)], limit=1)

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
