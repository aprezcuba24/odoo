# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class OrderBridgePushToken(models.Model):
    _name = 'order_bridge.push_token'
    _description = 'Registro FCM del dispositivo (token y plataforma)'

    device_id = fields.Many2one(
        'order_bridge.device',
        string='Dispositivo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        related='device_id.partner_id',
        store=True,
        index=True,
        readonly=True,
    )
    fcm_token = fields.Text(string='Token FCM', required=True)
    platform = fields.Selection(
        [('android', 'Android'), ('ios', 'iOS')],
        string='Plataforma',
        required=True,
    )
    last_seen_at = fields.Datetime(
        string='Última actividad token',
        required=True,
    )

    _sql_constraints = [
        ('order_bridge_push_token_device_uniq', 'unique(device_id)', 'Solo un registro FCM por dispositivo.'),
    ]

    @api.model
    def order_bridge_upsert_for_device(
        self,
        device,
        fcm_token,
        platform,
    ):
        """Create or update the single push row for this device (idempotent for token rotation)."""
        if not fcm_token or not str(fcm_token).strip():
            return self.browse()
        fcm_token = str(fcm_token).strip()
        self = self.sudo()
        now = fields.Datetime.now()
        existing = self.search([('device_id', '=', device.id)], limit=1)
        vals = {
            'fcm_token': fcm_token,
            'platform': platform,
            'last_seen_at': now,
        }
        if existing:
            existing.write(vals)
            return existing
        return self.create(
            {
                'device_id': device.id,
                'fcm_token': fcm_token,
                'platform': platform,
                'last_seen_at': now,
            }
        )

    @api.model
    def order_bridge_tokens_for_partners(self, partner_ids, active_devices_only=True):
        """Return deduplicated FCM token strings for the given partners (active devices with push rows)."""
        if not partner_ids:
            return []
        self = self.sudo()
        domain = [('partner_id', 'in', list(partner_ids))]
        if active_devices_only:
            domain.append(('device_id.active', '=', True))
        recs = self.search(domain)
        seen = set()
        out = []
        for r in recs:
            t = (r.fcm_token or '').strip()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out
