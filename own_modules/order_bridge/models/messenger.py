# Part of Odoo. See LICENSE file for full copyright and licensing details.

import secrets

from odoo import api, fields, models


class OrderBridgeMessenger(models.Model):
    _name = 'order_bridge.messenger'
    _description = 'Mensajero API móvil de entregas'
    _order = 'name, id'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        ondelete='cascade',
        index=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    api_key = fields.Char(
        string='Clave API',
        required=True,
        copy=False,
        index='btree',
        readonly=True,
        default=lambda self: self._default_api_key(),
    )

    _api_key_unique = models.Constraint(
        'unique(api_key)',
        'La clave API del mensajero debe ser única.',
    )

    @api.model
    def _default_api_key(self):
        return secrets.token_urlsafe(32)

    def action_regenerate_api_key(self):
        for messenger in self:
            messenger.api_key = self._default_api_key()
        return True
