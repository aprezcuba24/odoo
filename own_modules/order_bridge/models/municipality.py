# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OrderBridgeMunicipality(models.Model):
    _name = 'order_bridge.municipality'
    _description = 'Municipio (Tienda Apk)'
    _order = 'name, id'

    name = fields.Char(required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    neighborhood_ids = fields.One2many(
        'order_bridge.neighborhood', 'municipality_id', string='Barrios'
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Ya existe un municipio con ese nombre.'),
    ]

    @api.ondelete(at_uninstall=False)
    def _unlink_except_if_used_in_address(self):
        Address = self.env['order_bridge.partner_address'].sudo()
        for rec in self:
            if Address.search_count([('municipality_id', '=', rec.id)]):
                raise UserError(
                    _('No se puede eliminar el municipio porque está asignado a una dirección Tienda Apk.')
                )
            if rec.neighborhood_ids:
                raise UserError(
                    _('No se puede eliminar el municipio mientras tenga barrios. Elimine primero los barrios.')
                )


class OrderBridgeNeighborhood(models.Model):
    _name = 'order_bridge.neighborhood'
    _description = 'Barrio (Tienda Apk)'
    _order = 'name, id'

    name = fields.Char(required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    municipality_id = fields.Many2one(
        'order_bridge.municipality',
        required=True,
        ondelete='restrict',
        index=True,
    )

    _sql_constraints = [
        (
            'municipality_name_unique',
            'unique(municipality_id, name)',
            'Ya existe un barrio con ese nombre en este municipio.',
        ),
    ]

    @api.ondelete(at_uninstall=False)
    def _unlink_except_if_used_in_address(self):
        Address = self.env['order_bridge.partner_address'].sudo()
        for rec in self:
            if Address.search_count([('neighborhood_id', '=', rec.id)]):
                raise UserError(
                    _('No se puede eliminar el barrio porque está asignado a una dirección Tienda Apk.')
                )
