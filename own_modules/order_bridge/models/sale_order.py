# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    order_bridge_origin = fields.Selection(
        selection=[
            ('app', 'Client app'),
            ('admin', 'Administrator'),
        ],
        string='Order bridge origin',
        index=True,
    )
    order_bridge_device_id = fields.Many2one(
        'order_bridge.device', string='API device', ondelete='set null'
    )
    order_bridge_device_validated = fields.Boolean(
        string='Device validated at order',
        help='Snapshot at creation: whether the client device was validated when the order was placed.',
        readonly=True,
        copy=False,
    )
    order_bridge_ref = fields.Char(string='Bridge reference', copy=False, index=True)
    order_bridge_pos_config_id = fields.Many2one(
        'pos.config',
        string='Bridge POS config',
        help='Point of sale configuration whose product catalog applied when this order was created from the API.',
        readonly=True,
        copy=False,
        ondelete='set null',
        check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if vals.get('order_bridge_origin') and not vals.get('order_bridge_ref'):
                ref = seq.next_by_code('order_bridge.order.ref')
                if ref:
                    vals['order_bridge_ref'] = ref
            origin = vals.get('order_bridge_origin')
            if origin == 'admin':
                vals.setdefault('order_bridge_device_validated', True)
            elif origin == 'app':
                did = vals.get('order_bridge_device_id')
                if did:
                    dev = self.env['order_bridge.device'].browse(did)
                    vals.setdefault('order_bridge_device_validated', dev.phone_validated)
                else:
                    vals.setdefault('order_bridge_device_validated', False)
        return super().create(vals_list)
