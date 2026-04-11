# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

ADDRESS_FIELD_NAMES = ('street', 'neighborhood', 'municipality', 'state')


class OrderBridgePartnerAddress(models.Model):
    _name = 'order_bridge.partner_address'
    _description = 'Dirección de entrega del contacto (API Tienda Apk)'

    partner_id = fields.Many2one(
        'res.partner', required=True, ondelete='cascade', index=True
    )
    street = fields.Char(string='Dirección')
    neighborhood = fields.Char()
    municipality = fields.Char()
    state = fields.Char(string='Estado / provincia')

    _sql_constraints = [
        ('partner_unique', 'unique(partner_id)', 'Solo una dirección Tienda Apk por contacto.'),
    ]

    @api.model
    def order_bridge_put_full(self, partner, name, street, neighborhood, municipality, state):
        """Replace partner display name and full address (API PUT)."""
        partner = partner.sudo()
        self = self.sudo()
        partner.write({'name': name})
        addr = self.search([('partner_id', '=', partner.id)], limit=1)
        vals = {
            'street': street,
            'neighborhood': neighborhood,
            'municipality': municipality,
            'state': state,
        }
        if addr:
            addr.write(vals)
        else:
            self.create({'partner_id': partner.id, **vals})

    @api.model
    def order_bridge_patch(self, partner, name=None, address=None):
        """Partial name/address update (API PATCH)."""
        partner = partner.sudo()
        self = self.sudo()
        if name is not None:
            partner.write({'name': name})
        if not address:
            return
        patch_vals = {}
        for key in ADDRESS_FIELD_NAMES:
            if key in address:
                val = address[key]
                patch_vals[key] = '' if val is None else str(val).strip()
        if not patch_vals:
            return
        record = self.search([('partner_id', '=', partner.id)], limit=1)
        if record:
            record.write(patch_vals)
        else:
            base = {k: '' for k in ADDRESS_FIELD_NAMES}
            base.update(patch_vals)
            self.create({'partner_id': partner.id, **base})


class OrderBridgeOrderAddressSnapshot(models.Model):
    _name = 'order_bridge.order_address_snapshot'
    _description = 'Instantánea de la dirección de entrega al crear un pedido Tienda Apk'

    sale_order_id = fields.Many2one(
        'sale.order', required=True, ondelete='cascade', index=True
    )
    street = fields.Char(string='Dirección', readonly=True)
    neighborhood = fields.Char(readonly=True)
    municipality = fields.Char(readonly=True)
    state = fields.Char(string='Estado / provincia', readonly=True)

    _sql_constraints = [
        ('sale_order_unique', 'unique(sale_order_id)', 'Una instantánea de dirección por pedido de venta.'),
    ]

