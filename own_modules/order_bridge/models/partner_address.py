# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

ADDRESS_FIELD_NAMES = ('street', 'neighborhood_id', 'municipality_id', 'state')


class OrderBridgePartnerAddress(models.Model):
    _name = 'order_bridge.partner_address'
    _description = 'Dirección de entrega del contacto (API Tienda Apk)'

    partner_id = fields.Many2one(
        'res.partner', required=True, ondelete='cascade', index=True
    )
    street = fields.Char(string='Dirección')
    neighborhood_id = fields.Many2one(
        'order_bridge.neighborhood',
        string='Barrio',
        required=True,
        ondelete='restrict',
        index=True,
    )
    municipality_id = fields.Many2one(
        'order_bridge.municipality',
        string='Municipio',
        required=True,
        ondelete='restrict',
        index=True,
    )
    state = fields.Char(string='Estado / provincia')

    _sql_constraints = [
        ('partner_unique', 'unique(partner_id)', 'Solo una dirección Tienda Apk por contacto.'),
    ]

    @api.constrains('municipality_id', 'neighborhood_id')
    def _check_neighborhood_municipality(self):
        for addr in self:
            if addr.neighborhood_id and addr.municipality_id:
                if addr.neighborhood_id.municipality_id != addr.municipality_id:
                    raise ValidationError(
                        _('El barrio debe pertenecer al municipio indicado en la dirección.')
                    )

    @api.model
    def order_bridge_put_full(
        self,
        partner,
        name,
        street,
        neighborhood_id,
        municipality_id,
        state,
    ):
        """Replace partner display name and full address (API PUT)."""
        partner = partner.sudo()
        self = self.sudo()
        self._order_bridge_validate_location_ids_standalone(municipality_id, neighborhood_id)
        partner.write({'name': name})
        addr = self.search([('partner_id', '=', partner.id)], limit=1)
        vals = {
            'street': street,
            'neighborhood_id': neighborhood_id,
            'municipality_id': municipality_id,
            'state': state,
        }
        if addr:
            addr.write(vals)
        else:
            self.create({'partner_id': partner.id, **vals})

    @api.model
    def _order_bridge_validate_location_ids_standalone(self, municipality_id, neighborhood_id):
        if not municipality_id or not neighborhood_id:
            raise UserError(_('Debe indicar municipio y barrio.'))
        Municipality = self.env['order_bridge.municipality'].sudo()
        Neighborhood = self.env['order_bridge.neighborhood'].sudo()
        municipality = Municipality.browse(municipality_id).exists()
        if not municipality:
            raise UserError(_('Municipio no válido.'))
        neighborhood = Neighborhood.browse(neighborhood_id).exists()
        if not neighborhood:
            raise UserError(_('Barrio no válido.'))
        if neighborhood.municipality_id != municipality:
            raise UserError(_('El barrio no pertenece al municipio indicado.'))

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
            if key not in address:
                continue
            val = address[key]
            if key in ('neighborhood_id', 'municipality_id'):
                if val is None:
                    patch_vals[key] = False
                else:
                    patch_vals[key] = int(val)
            else:
                patch_vals[key] = '' if val is None else str(val).strip()
        if not patch_vals:
            return
        record = self.search([('partner_id', '=', partner.id)], limit=1)
        if record:
            m_id = record.municipality_id.id if record.municipality_id else False
            n_id = record.neighborhood_id.id if record.neighborhood_id else False
            if 'municipality_id' in patch_vals:
                m_id = patch_vals['municipality_id']
            if 'neighborhood_id' in patch_vals:
                n_id = patch_vals['neighborhood_id']
        else:
            m_id = patch_vals.get('municipality_id', False)
            n_id = patch_vals.get('neighborhood_id', False)
        self._order_bridge_validate_location_ids_standalone(m_id, n_id)
        if record:
            record.write(patch_vals)
        else:
            base = {
                'street': '',
                'state': '',
                'neighborhood_id': False,
                'municipality_id': False,
            }
            base.update(patch_vals)
            self.create({'partner_id': partner.id, **base})


class OrderBridgeOrderAddressSnapshot(models.Model):
    _name = 'order_bridge.order_address_snapshot'
    _description = 'Instantánea de la dirección de entrega al crear un pedido Tienda Apk'

    sale_order_id = fields.Many2one(
        'sale.order', required=True, ondelete='cascade', index=True
    )
    street = fields.Char(string='Dirección', readonly=True)
    neighborhood_id = fields.Many2one(
        'order_bridge.neighborhood',
        string='Barrio',
        readonly=True,
        ondelete='set null',
    )
    municipality_id = fields.Many2one(
        'order_bridge.municipality',
        string='Municipio',
        readonly=True,
        ondelete='set null',
    )
    state = fields.Char(string='Estado / provincia', readonly=True)

    _sql_constraints = [
        ('sale_order_unique', 'unique(sale_order_id)', 'Una instantánea de dirección por pedido de venta.'),
    ]
