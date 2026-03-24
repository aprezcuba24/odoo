# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    mobile_device_ids = fields.One2many('mobile.device', 'partner_id', string='Mobile devices')
    mobile_app_registered = fields.Boolean(
        string='Mobile app registered',
        compute='_compute_mobile_app_flags',
        store=True,
    )
    mobile_phone_validated = fields.Boolean(
        string='Mobile phone validated',
        compute='_compute_mobile_app_flags',
        store=True,
    )
    mobile_order_count = fields.Integer(
        string='Mobile orders',
        compute='_compute_mobile_order_count',
    )

    @api.depends('mobile_device_ids.active', 'mobile_device_ids.phone_validated')
    def _compute_mobile_app_flags(self):
        for partner in self:
            active_devices = partner.mobile_device_ids.filtered('active')
            partner.mobile_app_registered = bool(active_devices)
            partner.mobile_phone_validated = bool(active_devices.filtered('phone_validated'))

    @api.depends('mobile_device_ids')
    def _compute_mobile_order_count(self):
        SaleOrder = self.env['sale.order'].sudo()
        for partner in self:
            partner.mobile_order_count = SaleOrder.search_count([
                ('partner_id', '=', partner.id),
                ('mobile_origin', '!=', False),
            ])

    def action_open_mobile_devices(self):
        self.ensure_one()
        return {
            'name': _('Mobile devices'),
            'type': 'ir.actions.act_window',
            'res_model': 'mobile.device',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_open_mobile_orders(self):
        self.ensure_one()
        return {
            'name': _('Mobile orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id), ('mobile_origin', '!=', False)],
        }
