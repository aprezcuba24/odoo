# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mobile_origin = fields.Selection(
        selection=[
            ('app', 'Mobile app'),
            ('admin', 'Administrator'),
        ],
        string='Mobile origin',
        index=True,
    )
    mobile_device_id = fields.Many2one('mobile.device', string='Mobile device', ondelete='set null')
    mobile_device_validated = fields.Boolean(
        string='Device validated at order',
        help='Snapshot at creation: whether the mobile device was validated when the order was placed.',
        readonly=True,
        copy=False,
    )
    mobile_order_ref = fields.Char(string='Mobile reference', copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if vals.get('mobile_origin') and not vals.get('mobile_order_ref'):
                ref = seq.next_by_code('mobile.order.ref')
                if ref:
                    vals['mobile_order_ref'] = ref
            origin = vals.get('mobile_origin')
            if origin == 'admin':
                vals.setdefault('mobile_device_validated', True)
            elif origin == 'app':
                did = vals.get('mobile_device_id')
                if did:
                    dev = self.env['mobile.device'].browse(did)
                    vals.setdefault('mobile_device_validated', dev.phone_validated)
                else:
                    vals.setdefault('mobile_device_validated', False)
        return super().create(vals_list)
