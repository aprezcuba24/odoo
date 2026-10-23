# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
from collections import defaultdict

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tools.float_utils import float_compare

from odoo.addons.order_bridge.utils import order_stock
from odoo.addons.order_bridge.utils.constant import (
    API_LANG,
    DEFAULT_STORE_STATE,
    MESSENGER_NOTE_ACTIVITY_SUMMARY,
    STATE_CANCELED,
    STATE_DELIVERED,
    STATE_NEGOTIATING,
    STATE_READY_FOR_DELIVERY,
    STORE_STATE_VALID_CHOICES,
    ORDER_BRIDGE_ALLOWED_STORE_TRANSITIONS,
)
from odoo.addons.order_bridge.utils.order_contact import (
    address_text,
    delivery_address_text,
    order_phone,
)
from odoo.addons.order_bridge.listeners.order_created_listener import order_bridge_order_created
from odoo.addons.order_bridge.listeners.store_state_listener import order_bridge_store_state_changed
from odoo.addons.order_bridge.listeners.store_state_push_listener import order_bridge_store_state_push

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'order_bridge.dispatch.mixin']
    _LISTENERS = [
        (order_bridge_store_state_changed, 'order_bridge_sale_changed'),
        (order_bridge_store_state_push, 'order_bridge_sale_changed'),
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
    order_bridge_partner_has_map_point = fields.Boolean(
        related='partner_id.order_bridge_has_map_point',
        string='Coordenadas',
        store=True,
        readonly=True,
        help=(
            'Indica si el cliente del pedido tiene latitud y longitud configuradas '
            'en su dirección Tienda Apk.'
        ),
    )
    order_bridge_ref = fields.Char(string='Referencia tienda', copy=False, index=True)
    order_bridge_client_order_id = fields.Char(
        string='Id. pedido cliente',
        copy=False,
        index=True,
        help='Clave de idempotencia enviada por la app móvil al crear el pedido.',
    )
    order_bridge_promo_code = fields.Char(
        string='Código promocional',
        readonly=True,
        copy=False,
        help='Código promocional aplicado al crear el pedido por la API.',
    )
    order_bridge_snapshot_address_id = fields.Many2one(
        'order_bridge.order_address_snapshot',
        string='Instantánea de dirección de entrega',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    order_bridge_order_contact = fields.Text(
        string='Datos de entrega del pedido',
        compute='_compute_order_bridge_contact_summaries',
    )
    order_bridge_customer_contact = fields.Text(
        string='Datos actuales del cliente',
        compute='_compute_order_bridge_contact_summaries',
    )
    order_bridge_store_state = fields.Selection(
        selection=STORE_STATE_VALID_CHOICES,
        string='Estado tienda',
        default=DEFAULT_STORE_STATE,
        tracking=True,
        index=True,
    )
    order_bridge_messenger_id = fields.Many2one(
        'order_bridge.messenger',
        string='Mensajero',
        ondelete='set null',
        index=True,
        check_company=True,
        help='Mensajero al que se asigna este pedido para la API móvil de entregas.',
    )
    order_bridge_delivery_received_at = fields.Char(
        string='Entrega confirmada (servidor)',
        copy=False,
        readonly=True,
        help='ISO-8601 exacto devuelto a la APK en la primera confirmación de entrega.',
    )
    order_bridge_delivery_device_at = fields.Char(
        string='Entrega marcada (dispositivo)',
        copy=False,
        readonly=True,
        help='deviceTimestamp ISO-8601 enviado por la APK al marcar la entrega.',
    )
    order_bridge_delivery_note_ids = fields.One2many(
        'order_bridge.delivery.note',
        'order_id',
        string='Notas de entrega',
        copy=False,
    )
    order_bridge_unread_messenger_note = fields.Boolean(
        string='Notas del mensajero sin revisar',
        default=False,
        copy=False,
        index=True,
        help='Hay notas del mensajero pendientes de revisión en este pedido.',
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

    def _order_bridge_product_lines(self):
        """Product lines that consume stock for Tienda Apk checks."""
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and not l.is_downpayment and l.product_id
        )

    def _order_bridge_storable_qty_by_product(self):
        """Return ``{product: qty_in_product_uom}`` for storable lines."""
        self.ensure_one()
        qty_by_product = defaultdict(float)
        for line in self._order_bridge_product_lines():
            product = line.product_id
            if product.type == 'service' or not product.is_storable:
                continue
            qty = line.product_uom_id._compute_quantity(
                line.product_uom_qty, product.uom_id, round=False,
            )
            qty_by_product[product] += qty
        return qty_by_product

    def _order_bridge_reserved_qty_by_product(self, warehouse):
        """Qty already reserved by this order under ``warehouse`` (product UoM)."""
        self.ensure_one()
        reserved = defaultdict(float)
        if not warehouse:
            return reserved
        stock_locs = self.env['stock.location'].search([
            ('id', 'child_of', warehouse.view_location_id.id),
        ])
        moves = self.picking_ids.move_ids.filtered(
            lambda m: m.product_id.is_storable
            and m.state not in ('done', 'cancel')
            and m.location_id in stock_locs,
        )
        for move in moves:
            reserved[move.product_id] += move.quantity
        return reserved

    def _order_bridge_assert_stock_available(self):
        """Raise UserError if warehouse free_qty cannot cover storable lines.

        For confirmed orders, free_qty already excludes this order's reservation; that
        reserved quantity is added back so edits can keep or increase lines within stock.
        """
        self.ensure_one()
        if self.order_bridge_origin not in ('app', 'admin'):
            return
        warehouse = self.warehouse_id or order_stock.get_order_bridge_warehouse(
            self.env, self.company_id,
        )
        if not warehouse:
            raise UserError(_('No hay almacén configurado para la compañía.'))
        precision = self.env['decimal.precision'].precision_get('Product Unit')
        qty_by_product = self._order_bridge_storable_qty_by_product()
        if not qty_by_product:
            return
        reserved_by_product = self._order_bridge_reserved_qty_by_product(warehouse)
        shortages = []
        for product, need in qty_by_product.items():
            if float_compare(need, 0.0, precision_digits=precision) <= 0:
                continue
            free = product.with_context(warehouse_id=warehouse.id).free_qty
            available = free + reserved_by_product.get(product, 0.0)
            if float_compare(available, need, precision_digits=precision) < 0:
                shortages.append(
                    _(
                        '%(product)s (disponible: %(available)s)',
                        product=product.display_name,
                        available=available,
                    )
                )
        if shortages:
            raise UserError(
                _('Stock insuficiente: %(details)s', details=', '.join(shortages))
            )

    def _order_bridge_apply_promo_code(self, code):
        """Apply coupon/promo code via sale_loyalty. Raises UserError on failure."""
        self.ensure_one()
        code = code.strip()
        Lang = self.env['res.lang'].sudo()
        order = self.with_context(lang=API_LANG) if Lang._get_data(code=API_LANG) else self
        status = order._try_apply_code(code)
        if 'error' in status:
            if status.get('not_found'):
                raise UserError(
                    _('El código promocional no es válido (%s).', code)
                )
            raise UserError(status['error'])
        if not status:
            raise UserError(_('El código no genera ningún descuento aplicable.'))
        for coupon, rewards in status.items():
            if len(rewards) != 1:
                raise UserError(_('El código tiene varias recompensas; no se puede aplicar por API.'))
            apply_status = order._apply_program_reward(rewards, coupon)
            if 'error' in apply_status:
                raise UserError(apply_status['error'])
        self.order_bridge_promo_code = code

    def _order_bridge_try_confirm(self):
        """Confirm Tienda Apk orders so sale_stock creates reservations (draft/sent only)."""
        self.ensure_one()
        # sale_loyalty writes reward lines from action_confirm while the order is still
        # draft. Those writes must not start another confirmation.
        if self.env.context.get('order_bridge_confirming'):
            return
        if (
            self.order_bridge_origin not in ('app', 'admin')
            or self.state not in ('draft', 'sent')
            or self.locked
        ):
            return
        lines = self._order_bridge_product_lines()
        if not lines:
            return
        storable = lines.mapped('product_id').filtered('is_storable')
        if storable:
            order_stock.lock_products_for_stock(self.env, storable)
        self._order_bridge_assert_stock_available()
        self.with_context(order_bridge_confirming=True).action_confirm()
        self._order_bridge_reserve_stock_moves()

    def _order_bridge_sync_stock_after_line_write(self):
        """Confirm/reserve after lines change, or re-check stock on confirmed orders."""
        self.ensure_one()
        if self.env.context.get('order_bridge_confirming'):
            return
        if self.order_bridge_origin not in ('app', 'admin') or self.locked:
            return
        if self.state in ('draft', 'sent'):
            self._order_bridge_try_confirm()
            return
        if self.state != 'sale':
            return
        lines = self._order_bridge_product_lines()
        storable = lines.mapped('product_id').filtered('is_storable')
        if storable:
            order_stock.lock_products_for_stock(self.env, storable)
        self._order_bridge_assert_stock_available()
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

    def action_order_bridge_prepare_messaging(self):
        """Return the messaging guide PDF for selected ready-for-delivery store orders."""
        if not self:
            raise UserError(_('Seleccione al menos un pedido.'))
        for order in self:
            if order.order_bridge_origin not in ('app', 'admin'):
                raise UserError(
                    _(
                        'El pedido %(name)s no es un pedido de Tienda Apk.',
                        name=order.display_name,
                    )
                )
            if order.order_bridge_store_state != STATE_READY_FOR_DELIVERY:
                raise UserError(
                    _(
                        'El pedido %(name)s debe estar en Listo para entrega '
                        'para preparar la mensajería.',
                        name=order.display_name,
                    )
                )
        report = self.env.ref('order_bridge.action_report_messaging_guide')
        local_dt = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        generated_at = local_dt.strftime('%d/%m/%Y %H:%M')
        pdf_content, _report_format = self.env['ir.actions.report']._render_qweb_pdf(
            report.report_name,
            res_ids=self.ids,
            data={'generated_at': generated_at},
        )
        filename = local_dt.strftime('Guia_mensajeria_%Y-%m-%d_%H-%M.pdf')
        return {
            'pdf_base64': base64.b64encode(pdf_content).decode(),
            'filename': filename,
            'mimetype': 'application/pdf',
        }

    def _order_bridge_customer_address(self):
        """Dirección Tienda Apk actual del cliente (registro vacío si no existe)."""
        self.ensure_one()
        return self.env['order_bridge.partner_address'].sudo().search(
            [('partner_id', '=', self.partner_id.id)], limit=1,
        )

    def _order_bridge_customer_phone(self):
        """Teléfono actual del cliente; si falta, el del dispositivo API."""
        self.ensure_one()
        phone = (self.partner_id.phone or '').strip()
        if not phone and self.order_bridge_device_id:
            phone = (self.order_bridge_device_id.phone or '').strip()
        return phone

    def _order_bridge_store_customer_snapshot(self):
        """Crea o sustituye la instantánea con los datos actuales del cliente.

        Devuelve False (sin cambios) si el cliente no tiene dirección Tienda Apk.
        """
        self.ensure_one()
        addr = self._order_bridge_customer_address()
        if not addr:
            return False
        vals = {
            'street': addr.street or '',
            'neighborhood_id': addr.neighborhood_id.id if addr.neighborhood_id else False,
            'municipality_id': addr.municipality_id.id if addr.municipality_id else False,
            'state': addr.state or '',
            'phone': self._order_bridge_customer_phone(),
            'latitude': addr.latitude or 0.0,
            'longitude': addr.longitude or 0.0,
        }
        snap = self.order_bridge_snapshot_address_id.sudo()
        if snap:
            snap.write(vals)
        else:
            snap = self.env['order_bridge.order_address_snapshot'].sudo().create(
                {'sale_order_id': self.id, **vals},
            )
            self.write({'order_bridge_snapshot_address_id': snap.id})
        return True

    @staticmethod
    def _order_bridge_contact_block(phone, address, latitude, longitude):
        coords = f'{latitude}, {longitude}' if latitude and longitude else '—'
        return _(
            'Teléfono: %(phone)s\nDirección: %(address)s\nCoordenadas: %(coords)s',
            phone=phone or '—',
            address=address or '—',
            coords=coords,
        )

    @api.depends(
        'order_bridge_snapshot_address_id.street',
        'order_bridge_snapshot_address_id.neighborhood_id',
        'order_bridge_snapshot_address_id.municipality_id',
        'order_bridge_snapshot_address_id.state',
        'order_bridge_snapshot_address_id.phone',
        'order_bridge_snapshot_address_id.latitude',
        'order_bridge_snapshot_address_id.longitude',
        'partner_id.phone',
        'partner_id.order_bridge_partner_address_ids.street',
        'partner_id.order_bridge_partner_address_ids.neighborhood_id',
        'partner_id.order_bridge_partner_address_ids.municipality_id',
        'partner_id.order_bridge_partner_address_ids.state',
        'partner_id.order_bridge_partner_address_ids.latitude',
        'partner_id.order_bridge_partner_address_ids.longitude',
        'order_bridge_device_id.phone',
    )
    def _compute_order_bridge_contact_summaries(self):
        for order in self:
            snap = order.order_bridge_snapshot_address_id.sudo()
            if snap:
                order.order_bridge_order_contact = self._order_bridge_contact_block(
                    (snap.phone or '').strip(),
                    address_text(snap),
                    snap.latitude,
                    snap.longitude,
                )
            else:
                order.order_bridge_order_contact = _('El pedido no tiene dirección.')
            addr = order._order_bridge_customer_address()
            order.order_bridge_customer_contact = self._order_bridge_contact_block(
                order._order_bridge_customer_phone(),
                address_text(addr),
                addr.latitude,
                addr.longitude,
            )

    def action_order_bridge_replace_with_customer_address(self):
        """Sustituye los datos de entrega del pedido por los actuales del cliente."""
        for order in self:
            if not order._order_bridge_store_customer_snapshot():
                raise UserError(
                    _(
                        'El cliente %(partner)s no tiene dirección Tienda Apk; '
                        'el pedido %(name)s no se ha modificado.',
                        partner=order.partner_id.display_name,
                        name=order.display_name,
                    )
                )
        return True

    def order_bridge_report_phone(self):
        self.ensure_one()
        return order_phone(self)

    def order_bridge_report_address(self):
        self.ensure_one()
        return delivery_address_text(self)

    def order_bridge_report_product_lines(self):
        """Product lines for the messaging guide (no sections/notes)."""
        self.ensure_one()
        return self.order_line.filtered(lambda l: not l.display_type and l.product_id)

    def order_bridge_report_admin_delivery_notes(self):
        """Admin delivery notes for the messaging guide (chronological)."""
        self.ensure_one()
        return self.order_bridge_delivery_note_ids.filtered(lambda n: n.author == 'admin')

    def _order_bridge_note_activity_user(self):
        """User who should receive the messenger-note activity."""
        self.ensure_one()
        if self.user_id:
            return self.user_id
        Users = self.env['res.users']
        company = self.company_id
        manager_group = self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False)
        salesman_group = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
        domain_base = [
            ('share', '=', False),
            ('active', '=', True),
            ('company_ids', 'in', company.id),
        ]
        if manager_group:
            user = Users.search(
                domain_base + [('all_group_ids', 'in', manager_group.id)],
                limit=1,
                order='id',
            )
            if user:
                return user
        if salesman_group:
            return Users.search(
                domain_base + [('all_group_ids', 'in', salesman_group.id)],
                limit=1,
                order='id',
            )
        return Users.browse()

    def _order_bridge_on_messenger_note(self, note):
        """Mark unread, post chatter copy and schedule one open activity."""
        self.ensure_one()
        self.sudo().write({'order_bridge_unread_messenger_note': True})
        messenger_name = note.messenger_id.name or _('Mensajero')
        self.sudo().message_post(
            body=_(
                'Nota del mensajero %(name)s: %(body)s',
                name=messenger_name,
                body=note.body,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        existing = self.activity_ids.filtered(
            lambda a: a.summary == MESSENGER_NOTE_ACTIVITY_SUMMARY
            and (not todo or a.activity_type_id == todo)
        )
        if existing:
            return
        user = self._order_bridge_note_activity_user()
        if not user:
            return
        self.sudo().activity_schedule(
            'mail.mail_activity_data_todo',
            summary=MESSENGER_NOTE_ACTIVITY_SUMMARY,
            note=note.body,
            user_id=user.id,
        )

    def action_order_bridge_mark_messenger_notes_reviewed(self):
        """Mark messenger notes reviewed, clear badge and close related activities."""
        for order in self:
            pending = order.order_bridge_delivery_note_ids.filtered(
                lambda n: n.author == 'messenger' and not n.reviewed
            )
            if pending:
                pending.write({'reviewed': True})
            order.order_bridge_unread_messenger_note = False
            activities = order.activity_ids.filtered(
                lambda a: a.summary == MESSENGER_NOTE_ACTIVITY_SUMMARY
            )
            if activities:
                activities.action_feedback(feedback=_('Notas del mensajero revisadas'))
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
        if vals.get('order_line') and not self.env.context.get('order_bridge_confirming'):
            for order in self:
                order._order_bridge_sync_stock_after_line_write()
        for order in self:
            old = previous_by_id.get(order.id)
            order.on_event('order_bridge_sale_changed', old, order)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            # Readonly origin is omitted by the web client unless force_save; restore from context.
            if not vals.get('order_bridge_origin') and (
                self.env.context.get('order_bridge_admin_create')
                or self.env.context.get('default_order_bridge_origin') == 'admin'
            ):
                vals['order_bridge_origin'] = 'admin'
            if vals.get('order_bridge_origin') and not vals.get('order_bridge_ref'):
                company_id = vals.get('company_id') or self.env.company.id
                ref = seq.with_company(company_id).next_by_code('order_bridge.order.ref')
                if ref:
                    vals['order_bridge_ref'] = ref
        records = super().create(vals_list)
        for order, vals in zip(records, vals_list):
            if vals.get('partner_id'):
                order._order_bridge_store_customer_snapshot()
            promo_code = self.env.context.get('order_bridge_promo_code')
            if promo_code:
                order._order_bridge_apply_promo_code(promo_code)
            order._order_bridge_try_confirm()
            order._order_bridge_schedule_order_created_notification()
        return records
