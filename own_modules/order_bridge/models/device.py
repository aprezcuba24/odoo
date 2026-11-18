# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.order_bridge.utils.phone_match import canonical_registration_phone

_CHANNEL_TOKEN_RE = re.compile(r'(?<![a-z])(?:web|apk)(?![a-z])', re.IGNORECASE)


def normalize_phone_for_registration(env, phone_raw, company=None):
    """Return a compact E.164 phone for registration (``+53…`` for 8 digits).

    ``env`` / ``company`` are kept for call-site compatibility and unused:
    legacy 8-digit numbers always use the fixed ``+53`` prefix.
    """
    return canonical_registration_phone(phone_raw)


def parse_client_channel(app_version):
    """Return ``web`` or ``apk`` from ``X-App-Version``; default ``apk`` if unclear.

    Identified only when exactly one of the tokens ``web`` / ``apk`` appears
    (case-insensitive, bounded by non-letters). Missing, empty, neither, or both
    → ``apk``.
    """
    if app_version is None:
        return 'apk'
    text = str(app_version).strip()
    if not text:
        return 'apk'
    found = {m.group(0).lower() for m in _CHANNEL_TOKEN_RE.finditer(text)}
    if found == {'web'}:
        return 'web'
    if found == {'apk'}:
        return 'apk'
    return 'apk'


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
    client_channel = fields.Selection(
        selection=[
            ('apk', 'APK'),
            ('web', 'Web'),
        ],
        string='Canal cliente',
        required=True,
        default='apk',
        index=True,
        help='Canal de cliente (APK o web). Se fija en el alta desde X-App-Version.',
    )

    _sql_constraints = [
        ('device_key_unique', 'unique(device_key)', 'La clave del dispositivo debe ser única.'),
    ]

    def action_validate_phone(self):
        self.write({'phone_validated': True})

    def action_revoke_validation(self):
        self.write({'phone_validated': False})

    def order_bridge_touch_last_activity(self, min_interval_seconds=60):
        """Best-effort last_activity update; skip if row is locked or recently touched.

        Uses ``FOR NO KEY UPDATE SKIP LOCKED`` so parallel API calls on the same
        device do not raise SerializationFailure and abort the request transaction.
        ``last_activity`` is telemetry only (inactivity cron); a skipped write is fine.
        """
        self.ensure_one()
        self.env.cr.execute(
            """
            UPDATE order_bridge_device
               SET last_activity = (now() AT TIME ZONE 'UTC'),
                   write_date = (now() AT TIME ZONE 'UTC')
             WHERE id IN (
                SELECT id FROM order_bridge_device
                 WHERE id = %s
                   AND (
                        last_activity IS NULL
                        OR last_activity < (now() AT TIME ZONE 'UTC')
                           - make_interval(secs => %s)
                   )
                 FOR NO KEY UPDATE SKIP LOCKED
             )
            """,
            (self.id, int(min_interval_seconds)),
            log_exceptions=False,
        )

    @api.model
    def order_bridge_sync_apk_version(self, device_key, apk_version):
        """Persist X-App-Version when it changes for the given device_key.

        Best-effort: skips the write if another transaction holds the row lock,
        avoiding SerializationFailure on concurrent last_activity / apk updates.
        """
        if not device_key or not apk_version:
            return
        device_key = str(device_key).strip()
        apk_version = str(apk_version).strip()
        if not device_key or not apk_version:
            return
        device = self.sudo().search([('device_key', '=', device_key)], limit=1)
        if not device or device.apk_version == apk_version:
            return
        self.env.cr.execute(
            """
            UPDATE order_bridge_device
               SET apk_version = %s,
                   write_date = (now() AT TIME ZONE 'UTC')
             WHERE id IN (
                SELECT id FROM order_bridge_device
                 WHERE id = %s
                   AND (apk_version IS DISTINCT FROM %s)
                 FOR NO KEY UPDATE SKIP LOCKED
             )
            """,
            (apk_version, device.id, apk_version),
            log_exceptions=False,
        )

    def _deactivate_other_devices_for_phone(
        self, normalized_phone, company, client_channel, keep_key=None,
    ):
        """One phone = one active device per company and client channel."""
        domain = [
            ('phone', '=', normalized_phone),
            ('active', '=', True),
            ('company_id', '=', company.id),
            ('client_channel', '=', client_channel),
        ]
        if keep_key:
            domain.append(('device_key', '!=', keep_key))
        others = self.sudo().search(domain)
        if others:
            others.write({'active': False})

    @api.model
    def register_or_get(
        self, phone_raw, device_key, device_info=None, company=None, app_version=None,
    ):
        """Register device or return existing state (idempotent on same device_key).

        ``company`` is required when registering a new device (multi-company).
        Existing devices are returned without re-checking company.
        ``app_version`` (``X-App-Version``) sets ``client_channel`` on create only.
        """
        self = self.sudo()
        if not device_key or not str(device_key).strip():
            raise UserError(_('La clave del dispositivo es obligatoria.'))
        device_key = str(device_key).strip()
        Partner = self.env['res.partner'].sudo()
        existing = self.search([('device_key', '=', device_key)], limit=1)
        if existing:
            # Shop phone may have linked the device to the company partner;
            # move it to a person contact so profile updates cannot rename the company.
            partner = existing.partner_id._order_bridge_detach_system_partner()
            return {
                'device': existing,
                'created': False,
                'partner': partner,
            }
        if not company:
            raise UserError(_('La compañía (company_slug) es obligatoria para registrar un dispositivo.'))
        company = company.sudo()
        if not phone_raw or not str(phone_raw).strip():
            raise UserError(_('El teléfono es obligatorio.'))
        normalized = normalize_phone_for_registration(self.env, phone_raw, company=company)
        if not normalized:
            raise UserError(
                _('El teléfono debe tener 8 dígitos o el formato +5353024637.')
            )
        # Never reuse res.company.partner_id / internal users (same phone as the shop).
        partner = Partner._order_bridge_find_or_create_customer(normalized, company)
        client_channel = parse_client_channel(app_version)
        self._deactivate_other_devices_for_phone(
            normalized, company, client_channel, keep_key=None,
        )
        create_vals = {
            'device_key': device_key,
            'partner_id': partner.id,
            'company_id': company.id,
            'phone': normalized,
            'phone_validated': False,
            'active': True,
            'device_info': device_info,
            'client_channel': client_channel,
        }
        if app_version is not None and str(app_version).strip():
            create_vals['apk_version'] = str(app_version).strip()
        device = self.create(create_vals)
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
