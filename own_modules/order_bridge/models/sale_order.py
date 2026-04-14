# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    order_bridge_origin = fields.Selection(
        selection=[
            ('app', 'App cliente'),
            ('admin', 'Administrador'),
        ],
        string='Origen Tienda Apk',
        index=True,
    )
    order_bridge_device_id = fields.Many2one(
        'order_bridge.device', string='Dispositivo API', ondelete='set null'
    )
    order_bridge_device_phone_validated = fields.Boolean(
        related='order_bridge_device_id.phone_validated',
        string='Teléfono del dispositivo validado',
        help=(
            'Indica si el dispositivo API vinculado a este pedido tiene el teléfono validado '
            'por la tienda en este momento. Se actualiza al cambiar el dispositivo o su estado '
            'de validación; es falso si no hay dispositivo asociado.'
        ),
        readonly=True,
    )
    order_bridge_ref = fields.Char(string='Referencia tienda', copy=False, index=True)
    order_bridge_snapshot_address_id = fields.Many2one(
        'order_bridge.order_address_snapshot',
        string='Instantánea de dirección de entrega',
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    def _order_bridge_try_confirm(self):
        """Confirm Tienda Apk orders so sale_stock creates reservations (draft/sent only)."""
        bridge = self.filtered(
            lambda o: o.order_bridge_origin in ('app', 'admin')
            and o.state in ('draft', 'sent')
            and not o.locked
        )
        for order in bridge:
            lines = order.order_line.filtered(
                lambda l: not l.display_type and not l.is_downpayment and l.product_id
            )
            if not lines:
                continue
            order.action_confirm()

    def write(self, vals):
        res = super().write(vals)
        self._order_bridge_try_confirm()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if vals.get('order_bridge_origin') and not vals.get('order_bridge_ref'):
                ref = seq.next_by_code('order_bridge.order.ref')
                if ref:
                    vals['order_bridge_ref'] = ref
        records = super().create(vals_list)
        PartnerAddress = self.env['order_bridge.partner_address'].sudo()
        Snapshot = self.env['order_bridge.order_address_snapshot'].sudo()
        for order, vals in zip(records, vals_list):
            if vals.get('order_bridge_origin') != 'app':
                continue
            pid = vals.get('partner_id')
            if pid:
                if isinstance(pid, (list, tuple)):
                    pid = pid[0]
            else:
                continue
            addr = PartnerAddress.search([('partner_id', '=', pid)], limit=1)
            if not addr:
                continue
            snap = Snapshot.create({
                'sale_order_id': order.id,
                'street': addr.street or '',
                'neighborhood_id': addr.neighborhood_id.id if addr.neighborhood_id else False,
                'municipality_id': addr.municipality_id.id if addr.municipality_id else False,
                'state': addr.state or '',
            })
            order.write({'order_bridge_snapshot_address_id': snap.id})
        records._order_bridge_try_confirm()
        return records
