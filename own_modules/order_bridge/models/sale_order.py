# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tools.float_utils import float_compare

from odoo.addons.order_bridge.utils import order_stock
from odoo.addons.order_bridge.utils.constant import (
    DEFAULT_STORE_STATE,
    STATE_CANCELED,
    STATE_DELIVERED,
    STATE_NEGOTIATING,
    STATE_READY_FOR_DELIVERY,
    STORE_STATE_VALID_CHOICES,
    ORDER_BRIDGE_ALLOWED_STORE_TRANSITIONS,
)
from odoo.addons.order_bridge.listeners.order_created_listener import order_bridge_order_created
from odoo.addons.order_bridge.listeners.store_state_listener import order_bridge_store_state_changed

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'order_bridge.dispatch.mixin']
    _LISTENERS = [
        (order_bridge_store_state_changed, 'order_bridge_store_state_changed'),
        (order_bridge_order_created, 'order_bridge_order_created'),
    ]

    order_bridge_origin = fields.Selection(
        selection=[
            ('app', 'App cliente'),
            ('admin', 'Administrador'),
        ],
        string='Origen Tienda Apk',
        index=True,
        readonly=True,
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
    order_bridge_client_order_id = fields.Char(
        string='Id. pedido cliente',
        copy=False,
        index=True,
        help='Clave de idempotencia enviada por la app móvil al crear el pedido.',
    )
    order_bridge_snapshot_address_id = fields.Many2one(
        'order_bridge.order_address_snapshot',
        string='Instantánea de dirección de entrega',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    order_bridge_store_state = fields.Selection(
        selection=STORE_STATE_VALID_CHOICES,
        string='Estado tienda',
        default=DEFAULT_STORE_STATE,
        tracking=True,
        index=True,
    )

    _sql_constraints = [
        (
            'order_bridge_client_order_id_device_unique',
            'unique(order_bridge_device_id, order_bridge_client_order_id)',
            'Ya existe un pedido con el mismo identificador de cliente para este dispositivo.',
        ),
    ]

    @api.model
    def order_bridge_find_idempotent(self, device, body):
        """Return existing order for device + body.client_order_id, or empty recordset."""
        client_order_id = getattr(body, 'client_order_id', None)
        if not client_order_id:
            return self.browse()
        return self.search([
            ('order_bridge_device_id', '=', device.id),
            ('order_bridge_client_order_id', '=', client_order_id),
        ], limit=1)

    def _order_bridge_schedule_order_created_notification(self):
        """Send Telegram after commit so rolled-back orders do not notify."""
        self.ensure_one()
        order_id = self.id
        dbname = self.env.cr.dbname

        @self.env.cr.postcommit.add
        def _send_order_created_telegram():
            with Registry(dbname).cursor() as cr:
                order = api.Environment(cr, SUPERUSER_ID, {})['sale.order'].browse(order_id).exists()
                if order:
                    order.on_event('order_bridge_order_created', None, order)

    def _order_bridge_reserve_stock_moves(self):
        """Reserve stock moves greedily from sublocations (highest free quantity first)."""
        precision = self.env['decimal.precision'].precision_get('Product Unit')
        Location = self.env['stock.location']
        for order in self:
            warehouse = order.warehouse_id
            if not warehouse:
                continue
            stock_locs = Location.search([('id', 'child_of', warehouse.view_location_id.id)])
            moves = order.picking_ids.move_ids.filtered(
                lambda m: m.state in ('confirmed', 'partially_available', 'waiting')
                and m.product_id.is_storable
                and m.location_id in stock_locs,
            )
            for move in moves:
                if move.move_line_ids:
                    move._do_unreserve()
                remaining = move.product_qty - move.quantity
                for location, free_qty in order_stock.warehouse_locations_by_free_qty(
                    self.env, move.product_id, warehouse,
                ):
                    if float_compare(remaining, 0.0, precision_digits=precision) <= 0:
                        break
                    taken = move._update_reserved_quantity(
                        min(remaining, free_qty), location, strict=True,
                    )
                    remaining -= taken
                if float_compare(remaining, 0.0, precision_digits=precision) > 0:
                    _logger.warning(
                        'order_bridge: reserva incompleta move=%s producto=%s falta=%.2f',
                        move.id,
                        move.product_id.display_name,
                        remaining,
                    )

    def _order_bridge_apply_promo_code(self, code):
        """Apply coupon/promo code via sale_loyalty. Raises UserError on failure."""
        self.ensure_one()
        status = self._try_apply_code(code.strip())
        if 'error' in status:
            raise UserError(status['error'])
        if not status:
            raise UserError(_('El código no genera ningún descuento aplicable.'))
        for coupon, rewards in status.items():
            if len(rewards) != 1:
                raise UserError(_('El código tiene varias recompensas; no se puede aplicar por API.'))
            apply_status = self._apply_program_reward(rewards, coupon)
            if 'error' in apply_status:
                raise UserError(apply_status['error'])

    def _order_bridge_try_confirm(self):
        """Confirm Tienda Apk orders so sale_stock creates reservations (draft/sent only)."""
        self.ensure_one()
        if (
            self.order_bridge_origin not in ('app', 'admin')
            or self.state not in ('draft', 'sent')
            or self.locked
        ):
            return
        lines = self.order_line.filtered(
            lambda l: not l.display_type and not l.is_downpayment and l.product_id
        )
        if not lines:
            return
        self.action_confirm()
        self._order_bridge_reserve_stock_moves()

    def _order_bridge_check_store_state_transition(self, old_ss, new_ss):
        self.ensure_one()
        if old_ss == new_ss:
            return
        if self.order_bridge_origin not in ('app', 'admin'):
            return
        allowed = ORDER_BRIDGE_ALLOWED_STORE_TRANSITIONS.get(old_ss)
        if not allowed or new_ss not in allowed:
            raise UserError(
                _(
                    'No se puede cambiar el estado tienda de %(old)s a %(new)s en el pedido %(name)s.',
                    old=dict(self._fields['order_bridge_store_state'].selection).get(
                        old_ss, old_ss or ''
                    ),
                    new=dict(self._fields['order_bridge_store_state'].selection).get(
                        new_ss, new_ss or ''
                    ),
                    name=self.display_name,
                )
            )

    def action_order_bridge_negotiate(self):
        self.write({'order_bridge_store_state': STATE_NEGOTIATING})
        return True

    def action_order_bridge_ready_for_delivery(self):
        self.write({'order_bridge_store_state': STATE_READY_FOR_DELIVERY})
        return True

    def action_order_bridge_delivered(self):
        self.write({'order_bridge_store_state': STATE_DELIVERED})
        return True

    def action_order_bridge_cancel_store(self):
        self.write({'order_bridge_store_state': STATE_CANCELED})
        return True

    def write(self, vals):
        if 'order_bridge_store_state' in vals:
            new_ss = vals['order_bridge_store_state']
            for order in self:
                order._order_bridge_check_store_state_transition(
                    order.order_bridge_store_state, new_ss
                )
        previous_by_id = {o.id: o.read()[0] for o in self}
        res = super().write(vals)
        for order in self:
            old = previous_by_id.get(order.id)
            order.on_event('order_bridge_store_state_changed', old, order)
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
            pid = vals.get('partner_id')
            if pid:
                if isinstance(pid, (list, tuple)):
                    pid = pid[0]
                addr = PartnerAddress.search([('partner_id', '=', pid)], limit=1)
                if addr:
                    snap = Snapshot.create({
                        'sale_order_id': order.id,
                        'street': addr.street or '',
                        'neighborhood_id': addr.neighborhood_id.id if addr.neighborhood_id else False,
                        'municipality_id': addr.municipality_id.id if addr.municipality_id else False,
                        'state': addr.state or '',
                    })
                    order.write({'order_bridge_snapshot_address_id': snap.id})
            promo_code = self.env.context.get('order_bridge_promo_code')
            if promo_code:
                order._order_bridge_apply_promo_code(promo_code)
            order._order_bridge_try_confirm()
            order._order_bridge_schedule_order_created_notification()
        return records
