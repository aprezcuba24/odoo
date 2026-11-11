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
    result = fields.Selection(
        selection=[
            ('processed', 'Procesado'),
            ('not_interested', 'Sin interés'),
        ],
        string='Resultado',
        index=True,
        copy=False,
        readonly=True,
    )
    backend_response = fields.Text(
        string='Respuesta para la app',
        copy=False,
        help='Markdown en español enviado a la APK en POST /payments (backendResponse).',
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

    _transfer_type_code_unique = models.Constraint(
        'unique(transfer_type, code)',
        'Ya existe una transferencia con ese tipo y código.',
    )

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for transfer in self:
            transfer.payment_count = len(transfer.payment_ids)

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
            if vals.get('result'):
                records |= super().create([vals])
            else:
                records |= self._register_from_ui(vals)
        return records

    def write(self, vals):
        locked = {'phone', 'amount', 'code', 'transfer_type', 'result', 'messenger_id'}
        if locked.intersection(vals) and not self.env.context.get('order_bridge_transfer_skip_process'):
            raise UserError(_('No se puede modificar una transferencia ya registrada.'))
        return super().write(vals)

    @api.model
    def _register_from_ui(self, vals):
        """Create a transfer from the Odoo UI using the same apply flow as the API."""
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

        messenger = False
        if vals.get('messenger_id'):
            messenger = self.env['order_bridge.messenger'].browse(vals['messenger_id']).exists()

        existing = self._find_by_code(transfer_type, code)
        if existing:
            raise UserError(
                _('Ya existe una transferencia con el código %(code)s.', code=code)
            )

        try:
            self.process_payment(
                company=company,
                phone=phone,
                amount=amount,
                code=code,
                transfer_type=transfer_type,
                messenger=messenger or None,
            )
        except LockError as exc:
            raise UserError(
                _('No se pudo registrar la transferencia: un pedido está bloqueado. Inténtelo de nuevo.')
            ) from exc

        transfer = self._find_by_code(transfer_type, code)
        if not transfer:
            raise UserError(_('No se pudo registrar la transferencia.'))
        return transfer

    @api.model
    def _find_by_code(self, transfer_type, code):
        return self.search(
            [('transfer_type', '=', transfer_type), ('code', '=', code)],
            limit=1,
        )

    @api.model
    def _find_mobile_by_code(self, code):
        return self._find_by_code('mobile', code)

    @api.model
    def _api_result(self, transfer):
        """Return ``(result, backend_response)`` for an existing transfer."""
        return transfer.result, transfer.backend_response or ''

    @api.model
    def _escape_backend_md(self, text):
        value = text or ''
        return (
            value
            .replace('\\', '\\\\')
            .replace('*', '\\*')
            .replace('_', '\\_')
            .replace('`', '\\`')
        )

    @api.model
    def _format_backend_amount(self, currency, amount):
        return currency.format(amount)

    @api.model
    def _backend_response_not_interested(self, partners, currency):
        lines = ['Ese teléfono **no espera** un pago.']
        for partner in partners:
            zero = self._format_backend_amount(currency, 0.0)
            lines.append('')
            lines.append(f'**{self._escape_backend_md(partner.name)}**')
            lines.append(f'Deuda anterior: {zero}')
            lines.append(f'Queda por pagar: {zero}')
        return '\n'.join(lines)

    @api.model
    def _backend_response_processed(self, partner_rows, leftover, currency):
        lines = ['**Pago registrado.**']
        for row in partner_rows:
            lines.append('')
            lines.append(f'**{self._escape_backend_md(row["name"])}**')
            lines.append(
                f'Deuda anterior: {self._format_backend_amount(currency, row["debt_before"])}'
            )
            lines.append(
                f'Se aplicó: {self._format_backend_amount(currency, row["applied"])}'
            )
            lines.append(
                f'Queda por pagar: {self._format_backend_amount(currency, row["remaining_due"])}'
            )
        rounding = currency.rounding or 0.01
        if float_compare(leftover, 0.0, precision_rounding=rounding) > 0:
            lines.append('')
            surplus = self._format_backend_amount(currency, leftover)
            lines.append(f'Sobra: **{surplus}** sin aplicar.')
        return '\n'.join(lines)

    @api.model
    def _partner_rows_from_payments(self, orders, payment_vals):
        """Build per-partner debt/applied rows in application order."""
        orders_by_id = {order.id: order for order in orders}
        debt_before = {}
        for order in orders:
            partner_id = order.partner_id.id
            debt_before[partner_id] = debt_before.get(partner_id, 0.0) + order.order_bridge_amount_due

        applied = {}
        partner_order = []
        for vals in payment_vals:
            order = orders_by_id[vals['order_id']]
            partner_id = order.partner_id.id
            if partner_id not in applied:
                partner_order.append(partner_id)
                applied[partner_id] = 0.0
            applied[partner_id] += vals['amount']

        rows = []
        for partner_id in partner_order:
            partner = self.env['res.partner'].browse(partner_id)
            before = debt_before.get(partner_id, 0.0)
            applied_amount = applied[partner_id]
            rows.append({
                'name': partner.name or partner.display_name or '',
                'debt_before': before,
                'applied': applied_amount,
                'remaining_due': before - applied_amount,
            })
        return rows

    @api.model
    def process_mobile_payment(self, messenger, phone, amount, code):
        """API helper: process a mobile notice for the messenger's company."""
        return self.process_payment(
            company=messenger.company_id,
            phone=phone,
            amount=amount,
            code=code,
            transfer_type='mobile',
            messenger=messenger,
        )

    @api.model
    def process_payment(
        self, *, company, phone, amount, code, transfer_type='mobile', messenger=None,
    ):
        """Idempotent payment notice: apply transfer amount to due orders.

        Returns ``(result, backend_response)`` where ``result`` is
        ``processed`` or ``not_interested``.
        Raises ``LockError`` when an order cannot be locked.
        """
        self = self.sudo()
        existing = self._find_by_code(transfer_type, code)
        if existing:
            return self._api_result(existing)

        currency = company.currency_id
        partners = self.env['res.partner'].sudo()._order_bridge_partners_by_phone(
            phone, company,
        )
        orders = self.env['sale.order'].sudo().search(
            [
                ('partner_id', 'in', partners.ids),
                ('company_id', '=', company.id),
                ('order_bridge_origin', 'in', ('app', 'admin')),
                ('order_bridge_amount_due', '>', 0),
            ],
            order='id asc',
        )

        if not partners or not orders:
            backend_response = self._backend_response_not_interested(
                partners, currency,
            )
            transfer, created = self._create_transfer(
                company=company,
                phone=phone,
                amount=amount,
                code=code,
                result='not_interested',
                transfer_type=transfer_type,
                messenger=messenger,
                backend_response=backend_response,
            )
            if not created:
                return self._api_result(transfer)
            return self._api_result(transfer)

        for order in orders:
            order.lock_for_update()
        orders.invalidate_recordset()

        orders = orders.filtered(lambda o: o.order_bridge_amount_due > 0).sorted('id')
        if orders:
            currency = orders[:1].currency_id

        if not orders:
            backend_response = self._backend_response_not_interested(
                partners, currency,
            )
            transfer, created = self._create_transfer(
                company=company,
                phone=phone,
                amount=amount,
                code=code,
                result='not_interested',
                transfer_type=transfer_type,
                messenger=messenger,
                currency=currency,
                backend_response=backend_response,
            )
            return self._api_result(transfer)

        transfer_method = self.env.ref('order_bridge.payment_method_transfer')
        remaining = float(amount)
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
            })
            remaining -= apply_amount

        if not payment_vals:
            backend_response = self._backend_response_not_interested(
                partners, currency,
            )
            transfer, created = self._create_transfer(
                company=company,
                phone=phone,
                amount=amount,
                code=code,
                result='not_interested',
                transfer_type=transfer_type,
                messenger=messenger,
                currency=currency,
                backend_response=backend_response,
            )
            return self._api_result(transfer)

        partner_rows = self._partner_rows_from_payments(orders, payment_vals)
        backend_response = self._backend_response_processed(
            partner_rows, remaining, currency,
        )
        transfer, created = self._create_transfer(
            company=company,
            phone=phone,
            amount=amount,
            code=code,
            result='processed',
            transfer_type=transfer_type,
            messenger=messenger,
            currency=currency,
            backend_response=backend_response,
        )
        if not created:
            return self._api_result(transfer)

        for vals in payment_vals:
            vals['transfer_id'] = transfer.id
        self.env['order_bridge.order.payment'].sudo().create(payment_vals)
        return self._api_result(transfer)

    @api.model
    def _create_transfer(
        self,
        *,
        company,
        phone,
        amount,
        code,
        result,
        transfer_type='mobile',
        messenger=None,
        currency=None,
        backend_response='',
    ):
        """Create a transfer row. Return ``(record, created)``.

        On unique-code collision, return the existing row and ``created=False``.
        """
        vals = {
            'transfer_type': transfer_type,
            'code': code,
            'phone': phone,
            'amount': amount,
            'result': result,
            'backend_response': backend_response or '',
            'messenger_id': messenger.id if messenger else False,
            'company_id': company.id,
            'currency_id': (currency or company.currency_id).id,
        }
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
