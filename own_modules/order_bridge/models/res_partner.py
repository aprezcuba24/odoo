# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    order_bridge_device_ids = fields.One2many(
        'order_bridge.device', 'partner_id', string='Dispositivos API'
    )
    order_bridge_registered = fields.Boolean(
        string='Registrado en Tienda Apk',
        compute='_compute_order_bridge_flags',
        store=True,
    )
    order_bridge_phone_validated = fields.Boolean(
        string='Teléfono validado (Tienda Apk)',
        compute='_compute_order_bridge_flags',
        store=True,
    )
    order_bridge_order_count = fields.Integer(
        string='Pedidos Tienda Apk',
        compute='_compute_order_bridge_order_count',
    )
    order_bridge_partner_address_ids = fields.One2many(
        'order_bridge.partner_address', 'partner_id', string='Dirección Tienda Apk'
    )
    order_bridge_municipality_id = fields.Many2one(
        'order_bridge.municipality',
        string='Municipio',
        compute='_compute_order_bridge_address_location',
        store=True,
        readonly=True,
    )
    order_bridge_neighborhood_id = fields.Many2one(
        'order_bridge.neighborhood',
        string='Barrio',
        compute='_compute_order_bridge_address_location',
        store=True,
        readonly=True,
    )

    @api.depends(
        'order_bridge_partner_address_ids.municipality_id',
        'order_bridge_partner_address_ids.neighborhood_id',
    )
    def _compute_order_bridge_address_location(self):
        for partner in self:
            addr = partner.order_bridge_partner_address_ids[:1]
            partner.order_bridge_municipality_id = addr.municipality_id
            partner.order_bridge_neighborhood_id = addr.neighborhood_id

    @api.depends('order_bridge_device_ids.active', 'order_bridge_device_ids.phone_validated')
    def _compute_order_bridge_flags(self):
        for partner in self:
            active_devices = partner.order_bridge_device_ids.filtered('active')
            partner.order_bridge_registered = bool(active_devices)
            partner.order_bridge_phone_validated = bool(active_devices.filtered('phone_validated'))

    @api.depends('order_bridge_device_ids')
    def _compute_order_bridge_order_count(self):
        SaleOrder = self.env['sale.order'].sudo()
        for partner in self:
            partner.order_bridge_order_count = SaleOrder.search_count([
                ('partner_id', '=', partner.id),
                ('order_bridge_origin', '!=', False),
            ])

    def action_open_order_bridge_devices(self):
        self.ensure_one()
        return {
            'name': _('Dispositivos API'),
            'type': 'ir.actions.act_window',
            'res_model': 'order_bridge.device',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_open_order_bridge_orders(self):
        self.ensure_one()
        return {
            'name': _('Pedidos Tienda Apk'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id), ('order_bridge_origin', '!=', False)],
        }
