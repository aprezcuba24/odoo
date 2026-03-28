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
    order_bridge_snapshot_address_id = fields.Many2one(
        'order_bridge.order_address_snapshot',
        string='Delivery address snapshot',
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    @api.model
    def _load_pos_data_fields(self, config):
        # pos_sale lists picking_ids and other fields that exist only when optional modules
        # (e.g. sale_stock) are installed — keep only names that exist on this registry.
        fields_list = super()._load_pos_data_fields(config)
        return [f for f in fields_list if f in self._fields]

    @api.model
    def _load_pos_data_read(self, records, config):
        # Same guard as _load_pos_data_fields (mixin calls read here; must not pass unknown names).
        if not config:
            raise ValueError("config must be provided to read PoS data.")
        fields = [f for f in self._load_pos_data_fields(config) if f in self._fields]
        return records.read(fields, load=False) or []

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
                'neighborhood': addr.neighborhood or '',
                'municipality': addr.municipality or '',
                'state': addr.state or '',
            })
            order.write({'order_bridge_snapshot_address_id': snap.id})
        return records
