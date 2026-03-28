# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.phone_validation.tools import phone_validation as phone_validation_tools

_logger = logging.getLogger(__name__)


def normalize_phone_for_registration(env, phone_raw):
    """Return a normalized phone string (E.164 when possible)."""
    if not phone_raw or not str(phone_raw).strip():
        return ''
    phone_raw = str(phone_raw).strip()
    company = env.company
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
    _description = 'Registered API client device'
    _order = 'registration_date desc, id desc'

    device_key = fields.Char(required=True, index='btree', readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    phone = fields.Char(required=True, index=True)
    phone_validated = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
    registration_date = fields.Datetime(default=fields.Datetime.now, required=True)
    last_activity = fields.Datetime()
    device_info = fields.Char(string='Device info')

    _sql_constraints = [
        ('device_key_unique', 'unique(device_key)', 'Device key must be unique.'),
    ]

    def action_validate_phone(self):
        self.write({'phone_validated': True})

    def action_revoke_validation(self):
        self.write({'phone_validated': False})

    def _deactivate_other_devices_for_phone(self, normalized_phone, keep_key=None):
        """One phone = one active device. Deactivate others with same normalized phone."""
        domain = [('phone', '=', normalized_phone), ('active', '=', True)]
        if keep_key:
            domain.append(('device_key', '!=', keep_key))
        others = self.sudo().search(domain)
        if others:
            others.write({'active': False})

    @api.model
    def register_or_get(self, phone_raw, device_key, device_info=None):
        """Register device or return existing state (idempotent on same device_key)."""
        self = self.sudo()
        if not device_key or not str(device_key).strip():
            raise UserError(_('Device key is required.'))
        device_key = str(device_key).strip()
        existing = self.search([('device_key', '=', device_key)], limit=1)
        if existing:
            return {
                'device': existing,
                'created': False,
                'partner': existing.partner_id,
            }
        normalized = normalize_phone_for_registration(self.env, phone_raw)
        if not normalized:
            raise UserError(_('Phone is required.'))
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search(
            ['|', ('phone', '=', normalized), ('phone_sanitized', '=', normalized)],
            limit=1,
        )
        if not partner:
            partner = Partner.create({
                'name': normalized,
                'phone': normalized,
            })
        else:
            vals = {}
            if partner.phone != normalized:
                vals['phone'] = normalized
            if vals:
                partner.write(vals)
        self._deactivate_other_devices_for_phone(normalized, keep_key=None)
        device = self.create({
            'device_key': device_key,
            'partner_id': partner.id,
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
