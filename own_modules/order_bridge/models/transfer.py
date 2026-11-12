# Part of Odoo. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import LockError, UserError, ValidationError
from odoo.tools import mute_logger
from odoo.tools.float_utils import float_compare


class OrderBridgeTransfer(models.Model):
    _name = 'order_bridge.transfer'
    _description = 'Transferencia Tienda Apk'
    _order = 'create_date desc, id desc'
    _check_company_auto = True

    transfer_type = fields.Selection(
        selection=[
            ('mobile', 'Aviso móvil'),
        ],
        string='Tipo',
        required=True,
        default='mobile',
        index=True,
    )
    code = fields.Char(
        string='Código',
        required=True,
        index=True,
        copy=False,
    )
    phone = fields.Char(string='Teléfono', required=True)
    amount = fields.Monetary(
        string='Importe',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        ondelete='cascade',
        index=True,
        default=lambda self: self.env.company,
    )
    messenger_id = fields.Many2one(
        'order_bridge.messenger',
        string='Mensajero',
        ondelete='set null',
        index=True,
        check_company=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        ondelete='set null',
        index=True,
        check_company=True,
        help='Cliente al que el administrador aplica el importe de esta transferencia.',
    )
    result = fields.Selection(
        selection=[
            ('processed', 'Procesado'),
            ('not_interested', 'Sin interés'),
        ],
        string='Resultado',
        index=True,
        copy=False,
        readonly=True,
        default='processed',
    )
    backend_response = fields.Text(
        string='Respuesta para la app',
        copy=False,
        help='Texto histórico enviado a la APK en avisos antiguos (backendResponse).',
    )
    active = fields.Boolean(
        string='Activa',
        default=True,
        readonly=True,
        index=True,
        copy=False,
        help='Las transferencias descartadas se ocultan por defecto y pueden recuperarse.',
    )
    payment_ids = fields.One2many(
        'order_bridge.order.payment',
        'transfer_id',
        string='Cobros',
    )
    payment_count = fields.Integer(
        string='Nº cobros',
        compute='_compute_payment_count',
    )
    applied = fields.Boolean(
        string='Aplicada a deuda',
        compute='_compute_applied',
        store=True,
        index=True,
        help='Indica si esta transferencia ya tiene cobros aplicados a pedidos con deuda.',
    )

    _transfer_type_code_unique = models.Constraint(
        'unique(transfer_type, code)',
        'Ya existe una transferencia con ese tipo y código.',
    )

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for transfer in self:
            transfer.payment_count = len(transfer.payment_ids)

    @api.depends('payment_ids')
    def _compute_applied(self):
        for transfer in self:
            transfer.applied = bool(transfer.payment_ids)

    @api.constrains('amount')
    def _check_amount_positive(self):
        for transfer in self:
            rounding = transfer.currency_id.rounding or 0.01
            if float_compare(transfer.amount, 0.0, precision_rounding=rounding) <= 0:
                raise ValidationError(_('El importe de la transferencia debe ser mayor que cero.'))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('order_bridge_transfer_skip_process'):
            return super().create(vals_list)

        records = self.browse()
        for vals in vals_list:
            records |= self._register_notice(vals)
        return records

    def write(self, vals):
        locked = {'phone', 'amount', 'code', 'transfer_type', 'result', 'messenger_id'}
        if locked.intersection(vals) and not self.env.context.get('order_bridge_transfer_skip_process'):
            raise UserError(_('No se puede modificar una transferencia ya registrada.'))
        if 'partner_id' in vals and any(transfer.applied for transfer in self):
            raise UserError(
                _('No se puede cambiar el cliente de una transferencia que ya tiene cobros.')
            )
        return super().write(vals)

    @api.model
    def _register_notice(self, vals):
        """Create a transfer notice without applying payments."""
        phone = (vals.get('phone') or '').strip()
        code = (vals.get('code') or '').strip()
        amount = vals.get('amount')
        transfer_type = vals.get('transfer_type') or 'mobile'
        company = self.env['res.company'].browse(
            vals.get('company_id') or self.env.company.id
        ).exists()
        if not company:
            company = self.env.company

        if not phone:
            raise UserError(_('El teléfono es obligatorio.'))
        if not code:
            raise UserError(_('El código es obligatorio.'))
        try:
            amount = float(amount)
        except (TypeError, ValueError) as exc:
            raise UserError(_('El importe debe ser un número mayor que cero.')) from exc
        if amount <= 0:
            raise UserError(_('El importe debe ser un número mayor que cero.'))

        existing = self._find_by_code(transfer_type, code)
        if existing:
            if self.env.context.get('order_bridge_transfer_from_api'):
                return existing
            raise UserError(
                _('Ya existe una transferencia con el código %(code)s.', code=code)
            )

        messenger = False
        if vals.get('messenger_id'):
            messenger = self.env['order_bridge.messenger'].browse(vals['messenger_id']).exists()

        create_vals = {
            'transfer_type': transfer_type,
            'code': code,
            'phone': phone,
            'amount': amount,
            'result': 'processed',
            'backend_response': vals.get('backend_response') or '',
            'messenger_id': messenger.id if messenger else False,
            'company_id': company.id,
            'currency_id': vals.get('currency_id') or company.currency_id.id,
            'partner_id': vals.get('partner_id') or False,
        }
        transfer, created = self._create_transfer_row(create_vals)
        if not created and not self.env.context.get('order_bridge_transfer_from_api'):
            raise UserError(
                _('Ya existe una transferencia con el código %(code)s.', code=code)
            )
        return transfer

    @api.model
    def _find_by_code(self, transfer_type, code):
        return self.with_context(active_test=False).search(
            [('transfer_type', '=', transfer_type), ('code', '=', code)],
            limit=1,
        )

    @api.model
    def _api_result(self, transfer):
        """Return ``(result, backend_response)`` for an existing transfer."""
        return transfer.result, transfer.backend_response or ''

    @api.model
    def process_mobile_payment(self, messenger, phone, amount, code):
        """API helper: register a mobile notice without applying payments."""
        self = self.sudo().with_context(order_bridge_transfer_from_api=True)
        transfer = self._register_notice({
            'company_id': messenger.company_id.id,
            'phone': phone,
            'amount': amount,
            'code': code,
            'transfer_type': 'mobile',
            'messenger_id': messenger.id,
        })
        return self._api_result(transfer)

    @api.model
    def _create_transfer_row(self, vals):
        """Create a transfer row. Return ``(record, created)``.

        On unique-code collision, return the existing row and ``created=False``.
        """
        transfer_type = vals.get('transfer_type') or 'mobile'
        code = vals.get('code')
        try:
            with self.env.cr.savepoint(), mute_logger('odoo.sql_db'):
                return (
                    self.with_context(order_bridge_transfer_skip_process=True).create(vals),
                    True,
                )
        except IntegrityError:
            existing = self._find_by_code(transfer_type, code)
            if existing:
                return existing, False
            raise

    def action_apply_to_debt(self):
        """Apply this transfer amount to the selected partner's due store orders."""
        self.ensure_one()
        if self.applied:
            raise UserError(_('Esta transferencia ya tiene cobros aplicados.'))
        if not self.partner_id:
            raise UserError(_('Seleccione un cliente antes de aplicar la transferencia.'))

        orders = self.env['sale.order'].search(
            [
                ('partner_id', '=', self.partner_id.id),
                ('company_id', '=', self.company_id.id),
                ('order_bridge_origin', 'in', ('app', 'admin')),
                ('order_bridge_amount_due', '>', 0),
            ],
            order='id asc',
        )
        if not orders:
            raise UserError(_('El cliente seleccionado no tiene pedidos con deuda.'))

        try:
            for order in orders:
                order.lock_for_update()
        except LockError as exc:
            raise UserError(
                _('No se pudo aplicar la transferencia: un pedido está bloqueado. Inténtelo de nuevo.')
            ) from exc
        orders.invalidate_recordset()
        orders = orders.filtered(lambda o: o.order_bridge_amount_due > 0).sorted('id')
        if not orders:
            raise UserError(_('El cliente seleccionado no tiene pedidos con deuda.'))

        transfer_method = self.env.ref('order_bridge.payment_method_transfer')
        remaining = float(self.amount)
        payment_vals = []
        for order in orders:
            rounding = order.currency_id.rounding or 0.01
            due = order.order_bridge_amount_due
            if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
                break
            if float_compare(due, 0.0, precision_rounding=rounding) <= 0:
                continue
            apply_amount = remaining if remaining < due else due
            if float_compare(apply_amount, 0.0, precision_rounding=rounding) <= 0:
                continue
            payment_vals.append({
                'order_id': order.id,
                'method_id': transfer_method.id,
                'amount': apply_amount,
                'transfer_id': self.id,
            })
            remaining -= apply_amount

        if not payment_vals:
            raise UserError(_('El cliente seleccionado no tiene pedidos con deuda.'))

        self.env['order_bridge.order.payment'].create(payment_vals)
        return True

    def action_discard(self):
        """Hide transfers from the default list without deleting them."""
        self.action_archive()
        return True

    def action_recover(self):
        """Show previously discarded transfers again."""
        self.action_unarchive()
        return True

    def action_open_payments(self):
        self.ensure_one()
        return {
            'name': _('Cobros de la transferencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'order_bridge.order.payment',
            'view_mode': 'list,form',
            'domain': [('transfer_id', '=', self.id)],
            'context': {'default_transfer_id': self.id},
        }
