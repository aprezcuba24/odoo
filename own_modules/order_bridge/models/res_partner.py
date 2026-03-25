# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    order_bridge_device_ids = fields.One2many(
        'order_bridge.device', 'partner_id', string='API devices'
    )
    order_bridge_registered = fields.Boolean(
        string='Order bridge registered',
        compute='_compute_order_bridge_flags',
        store=True,
    )
    order_bridge_phone_validated = fields.Boolean(
        string='Order bridge phone validated',
        compute='_compute_order_bridge_flags',
        store=True,
    )
    order_bridge_order_count = fields.Integer(
        string='Bridge orders',
        compute='_compute_order_bridge_order_count',
    )

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
            'name': _('API devices'),
            'type': 'ir.actions.act_window',
            'res_model': 'order_bridge.device',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_open_order_bridge_orders(self):
        self.ensure_one()
        return {
            'name': _('Bridge orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id), ('order_bridge_origin', '!=', False)],
        }
