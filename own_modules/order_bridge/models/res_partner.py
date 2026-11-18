# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.float_utils import float_compare

from odoo.addons.order_bridge.utils.phone_match import phone_match_key


class ResPartner(models.Model):
    _inherit = 'res.partner'

    order_bridge_phone_key = fields.Char(
        string='Clave teléfono Tienda Apk',
        compute='_compute_order_bridge_phone_key',
        store=True,
        index=True,
        help=(
            'Clave normalizada del campo phone para equivalencias '
            '(p. ej. 53024637 y 5353024637).'
        ),
    )
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
    order_bridge_amount_due = fields.Monetary(
        string='Deuda Tienda Apk',
        compute='_compute_order_bridge_amount_due',
        search='_search_order_bridge_amount_due',
        currency_field='currency_id',
        help='Suma del saldo pendiente de cobro de los pedidos Tienda Apk de este cliente.',
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
    order_bridge_has_map_point = fields.Boolean(
        string='Coordenadas de mapa',
        compute='_compute_order_bridge_has_map_point',
        store=True,
        help=(
            'Indica si la dirección Tienda Apk del cliente tiene latitud y longitud '
            'distintas de cero (punto útil para el mapa de entregas).'
        ),
    )

    @api.depends('phone')
    def _compute_order_bridge_phone_key(self):
        for partner in self:
            partner.order_bridge_phone_key = phone_match_key(partner.phone) or False

    def _order_bridge_is_system_partner(self):
        """True if this contact is a company entity or an internal user.

        App customers must not share those partners: writing the profile name
        would rename ``res.company`` (related ``partner_id.name``).
        """
        self.ensure_one()
        if self.env['res.company'].sudo().search_count([('partner_id', '=', self.id)]):
            return True
        if self.user_ids.filtered(lambda u: u.active and not u.share):
            return True
        return False

    @api.model
    def _order_bridge_system_partner_ids(self):
        """Ids of company entity partners and internal-user partners."""
        company_partner_ids = self.env['res.company'].sudo().search([]).partner_id.ids
        user_partner_ids = self.env['res.users'].sudo().search([
            ('share', '=', False),
            ('active', '=', True),
        ]).partner_id.ids
        return list({*company_partner_ids, *user_partner_ids})

    @api.model
    def _order_bridge_find_or_create_customer(self, phone, company):
        """Find a non-system partner for the phone, or create a person contact."""
        phone = (phone or '').strip()
        if not phone:
            raise UserError(_('El teléfono es obligatorio.'))
        company = company.sudo()
        protected = self._order_bridge_system_partner_ids()
        key = phone_match_key(phone)
        phone_domain = [
            '|',
            ('phone', '=', phone),
            ('phone_sanitized', '=', phone),
        ]
        if key:
            phone_domain = ['|'] + phone_domain + [('order_bridge_phone_key', '=', key)]
        domain = phone_domain + [
            '|',
            ('company_id', '=', company.id),
            ('company_id', '=', False),
        ]
        if protected:
            domain = [('id', 'not in', protected)] + domain
        partner = self.sudo().search(domain, limit=1)
        if partner:
            vals = {}
            old_phone = (partner.phone or '').strip()
            if partner.phone != phone:
                vals['phone'] = phone
                if old_phone and partner.name == old_phone:
                    vals['name'] = phone
            if not partner.company_id:
                vals['company_id'] = company.id
            if vals:
                partner.write(vals)
            return partner
        return self.sudo().create({
            'name': phone,
            'phone': phone,
            'company_id': company.id,
        })

    def _order_bridge_detach_system_partner(self):
        """If this is a system partner, move API devices to a person contact.

        Leaves the company / user partner name untouched. Existing sale orders
        stay on the original partner.
        """
        self.ensure_one()
        if not self._order_bridge_is_system_partner():
            return self
        Device = self.env['order_bridge.device'].sudo()
        devices = Device.search([('partner_id', '=', self.id)])
        company = self.env['res.company'].sudo().search(
            [('partner_id', '=', self.id)],
            limit=1,
        )
        if not company and devices:
            company = devices[0].company_id
        if not company:
            company = self.company_id or self.env.company
        phone = (self.phone or '').strip()
        if not phone and devices:
            phone = (devices[0].phone or '').strip()
        customer = self._order_bridge_find_or_create_customer(phone, company)
        if devices:
            devices.write({'partner_id': customer.id})
        return customer

    def _search_phone_mobile_search(self, operator, value):
        domain = super()._search_phone_mobile_search(operator, value)
        if not isinstance(value, str):
            return domain
        key = phone_match_key(value)
        if not key:
            return domain
        min_len = getattr(self, '_phone_search_min_length', 3) or 0
        if min_len and len(key) < min_len:
            return domain
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, Domain('order_bridge_phone_key', '!=', key)])
        return Domain.OR([domain, Domain('order_bridge_phone_key', '=', key)])

    @api.depends(
        'order_bridge_partner_address_ids.municipality_id',
        'order_bridge_partner_address_ids.neighborhood_id',
    )
    def _compute_order_bridge_address_location(self):
        for partner in self:
            addr = partner.order_bridge_partner_address_ids[:1]
            partner.order_bridge_municipality_id = addr.municipality_id
            partner.order_bridge_neighborhood_id = addr.neighborhood_id

    @api.depends(
        'order_bridge_partner_address_ids.latitude',
        'order_bridge_partner_address_ids.longitude',
    )
    def _compute_order_bridge_has_map_point(self):
        for partner in self:
            addr = partner.order_bridge_partner_address_ids[:1]
            if not addr:
                partner.order_bridge_has_map_point = False
                continue
            lat = float(addr.latitude or 0.0)
            lon = float(addr.longitude or 0.0)
            partner.order_bridge_has_map_point = lat != 0.0 and lon != 0.0

    @api.depends('order_bridge_device_ids.active', 'order_bridge_device_ids.phone_validated')
    def _compute_order_bridge_flags(self):
        for partner in self:
            active_devices = partner.order_bridge_device_ids.filtered('active')
            partner.order_bridge_registered = bool(active_devices)
            partner.order_bridge_phone_validated = bool(active_devices.filtered('phone_validated'))

    def _order_bridge_store_order_domain(self):
        self.ensure_one()
        return [
            ('partner_id', '=', self.id),
            ('order_bridge_origin', 'in', ('app', 'admin')),
        ]

    def _compute_order_bridge_order_count(self):
        SaleOrder = self.env['sale.order'].sudo()
        for partner in self:
            partner.order_bridge_order_count = SaleOrder.search_count(
                partner._order_bridge_store_order_domain(),
            )

    def _compute_order_bridge_amount_due(self):
        SaleOrder = self.env['sale.order']
        for partner in self:
            orders = SaleOrder.search(partner._order_bridge_store_order_domain())
            partner.order_bridge_amount_due = sum(orders.mapped('order_bridge_amount_due'))

    def _search_order_bridge_amount_due(self, operator, value):
        if operator not in ('>', '>=', '<', '<=', '=', '!='):
            raise UserError(_('Operador de búsqueda no soportado para la deuda Tienda Apk.'))
        try:
            amount = float(value)
        except (TypeError, ValueError) as exc:
            raise UserError(_('Valor de búsqueda inválido para la deuda Tienda Apk.')) from exc

        groups = self.env['sale.order']._read_group(
            [('order_bridge_origin', 'in', ('app', 'admin'))],
            groupby=['partner_id'],
            aggregates=['order_bridge_amount_due:sum'],
        )
        matching_ids = []
        partners_with_orders = []
        for partner, total_due in groups:
            if not partner:
                continue
            partners_with_orders.append(partner.id)
            due = total_due or 0.0
            if self._order_bridge_compare_amount(due, operator, amount):
                matching_ids.append(partner.id)

        # Clientes sin pedidos de tienda tienen deuda 0.
        if self._order_bridge_compare_amount(0.0, operator, amount):
            if matching_ids and partners_with_orders:
                return ['|', ('id', 'in', matching_ids), ('id', 'not in', partners_with_orders)]
            if matching_ids:
                return [('id', 'in', matching_ids)]
            if partners_with_orders:
                return [('id', 'not in', partners_with_orders)]
            return [(1, '=', 1)]
        return [('id', 'in', matching_ids)]

    @api.model
    def _order_bridge_compare_amount(self, left, operator, right):
        rounding = self.env.company.currency_id.rounding or 0.01
        cmp_res = float_compare(left, right, precision_rounding=rounding)
        if operator == '>':
            return cmp_res > 0
        if operator == '>=':
            return cmp_res >= 0
        if operator == '<':
            return cmp_res < 0
        if operator == '<=':
            return cmp_res <= 0
        if operator == '=':
            return cmp_res == 0
        if operator == '!=':
            return cmp_res != 0
        return False

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
        list_view = self.env.ref('order_bridge.view_order_tree_order_bridge_store')
        return {
            'name': _('Pedidos Tienda Apk'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'views': [(list_view.id, 'list'), (False, 'form')],
            'domain': self._order_bridge_store_order_domain(),
            'context': {
                'default_partner_id': self.id,
                'default_order_bridge_origin': 'admin',
                'order_bridge_admin_create': True,
            },
        }

    def action_open_order_bridge_orders_with_due(self):
        self.ensure_one()
        list_view = self.env.ref('order_bridge.view_order_tree_order_bridge_store')
        return {
            'name': _('Pedidos con saldo pendiente'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'views': [(list_view.id, 'list'), (False, 'form')],
            'domain': self._order_bridge_store_order_domain() + [
                ('order_bridge_amount_due', '>', 0),
            ],
            'context': {
                'default_partner_id': self.id,
                'default_order_bridge_origin': 'admin',
                'order_bridge_admin_create': True,
            },
        }

    def action_order_bridge_fcm_send_wizard(self):
        self.ensure_one()
        return {
            'name': _('Enviar notificación push'),
            'type': 'ir.actions.act_window',
            'res_model': 'order_bridge.fcm.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_target_mode': 'single_partner',
                'default_partner_id': self.id,
            },
        }
