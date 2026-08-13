# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.phone_validation.tools import phone_validation as phone_validation_tools

_logger = logging.getLogger(__name__)


def normalize_phone_for_registration(env, phone_raw, company=None):
    """Return a normalized phone string (E.164 when possible)."""
    if not phone_raw or not str(phone_raw).strip():
        return ''
    phone_raw = str(phone_raw).strip()
    company = company or env.company
    country = company.country_id
    country_code = country.code if country else None
    phone_code = country.phone_code if country and country.phone_code else None
    try:
        return phone_validation_tools.phone_format(
            phone_raw, country_code, phone_code, force_format='E164'
        )
    except UserError:
        _logger.info('Phone format fallback for %r', phone_raw)
        return phone_raw


class OrderBridgeDevice(models.Model):
    _name = 'order_bridge.device'
    _description = 'Dispositivo cliente API registrado'
    _order = 'registration_date desc, id desc'
    _check_company_auto = True

    device_key = fields.Char(required=True, index='btree', readonly=True)
    partner_id = fields.Many2one(
        'res.partner',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        ondelete='cascade',
        index=True,
        default=lambda self: self.env.company,
    )
    phone = fields.Char(required=True, index=True)
    phone_validated = fields.Boolean(
        string='Teléfono validado',
        default=False,
        help=(
            'La tienda ha confirmado manualmente que el número de este dispositivo es correcto. '
            'Hasta entonces el cliente puede pedir, pero el canal se considera no validado.'
        ),
    )
    active = fields.Boolean(default=True)
    registration_date = fields.Datetime(default=fields.Datetime.now, required=True)
    last_activity = fields.Datetime()
    device_info = fields.Char(string='Información del dispositivo')
    apk_version = fields.Char(string='Versión APK')

    _sql_constraints = [
        ('device_key_unique', 'unique(device_key)', 'La clave del dispositivo debe ser única.'),
    ]

    def action_validate_phone(self):
        self.write({'phone_validated': True})

    def action_revoke_validation(self):
        self.write({'phone_validated': False})

    @api.model
    def order_bridge_sync_apk_version(self, device_key, apk_version):
        """Persist X-App-Version when it changes for the given device_key."""
        if not device_key or not apk_version:
            return
        device_key = str(device_key).strip()
        apk_version = str(apk_version).strip()
        if not device_key or not apk_version:
            return
        device = self.sudo().search([('device_key', '=', device_key)], limit=1)
        if device and device.apk_version != apk_version:
            device.write({'apk_version': apk_version})

    def _deactivate_other_devices_for_phone(self, normalized_phone, company, keep_key=None):
        """One phone = one active device per company. Deactivate others with same phone."""
        domain = [
            ('phone', '=', normalized_phone),
            ('active', '=', True),
            ('company_id', '=', company.id),
        ]
        if keep_key:
            domain.append(('device_key', '!=', keep_key))
        others = self.sudo().search(domain)
        if others:
            others.write({'active': False})

    @api.model
    def register_or_get(self, phone_raw, device_key, device_info=None, company=None):
        """Register device or return existing state (idempotent on same device_key).

        ``company`` is required when registering a new device (multi-company).
        Existing devices are returned without re-checking company.
        """
        self = self.sudo()
        if not device_key or not str(device_key).strip():
            raise UserError(_('La clave del dispositivo es obligatoria.'))
        device_key = str(device_key).strip()
        existing = self.search([('device_key', '=', device_key)], limit=1)
        if existing:
            return {
                'device': existing,
                'created': False,
                'partner': existing.partner_id,
            }
        if not company:
            raise UserError(_('La compañía (company_slug) es obligatoria para registrar un dispositivo.'))
        company = company.sudo()
        normalized = normalize_phone_for_registration(self.env, phone_raw, company=company)
        if not normalized:
            raise UserError(_('El teléfono es obligatorio.'))
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search(
            [
                '|',
                ('phone', '=', normalized),
                ('phone_sanitized', '=', normalized),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False),
            ],
            limit=1,
        )
        if not partner:
            partner = Partner.create({
                'name': normalized,
                'phone': normalized,
                'company_id': company.id,
            })
        else:
            vals = {}
            if partner.phone != normalized:
                vals['phone'] = normalized
            if not partner.company_id:
                vals['company_id'] = company.id
            if vals:
                partner.write(vals)
        self._deactivate_other_devices_for_phone(normalized, company, keep_key=None)
        device = self.create({
            'device_key': device_key,
            'partner_id': partner.id,
            'company_id': company.id,
            'phone': normalized,
            'phone_validated': False,
            'active': True,
            'device_info': device_info,
        })
        return {'device': device, 'created': True, 'partner': partner}

    @api.model
    def cron_deactivate_inactive_devices(self):
        """Deactivate devices with no activity for N days (system parameter)."""
        ICP = self.env['ir.config_parameter'].sudo()
        try:
            days = int(ICP.get_param('order_bridge.device_inactivity_days', '90'))
        except ValueError:
            days = 90
        if days <= 0:
            return
        threshold = fields.Datetime.now() - timedelta(days=days)
        stale = self.search([
            ('active', '=', True),
            '|',
            ('last_activity', '=', False),
            ('last_activity', '<', threshold),
        ])
        stale.write({'active': False})
