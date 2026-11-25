# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.modules.registry import Registry

from odoo.addons.order_bridge.utils.constant import ORDER_BRIDGE_ALLOWED_STORE_TRANSITIONS
from odoo.addons.order_bridge.utils.telegram_client import send_message

from ..utils.telegram_merchant_message import format_merchant_order_created_message


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    merchant_id = fields.Many2one(
        'merchant_store.merchant',
        string='Comerciante',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    client_checkout_id = fields.Char(
        string='Id. checkout cliente',
        copy=False,
        index=True,
        help='Clave de idempotencia que agrupa las subórdenes de un mismo checkout de la app.',
    )
    order_bridge_order_id = fields.Many2one(
        'sale.order',
        string='Pedido Tienda Apk',
        ondelete='set null',
        index=True,
        copy=False,
        help='Pedido propio de Tienda Apk creado en el mismo checkout (opcional).',
    )

    _merchant_store_checkout_merchant_unique = models.Constraint(
        'unique(company_id, client_checkout_id, merchant_id)',
        'Ya existe una suborden para este comerciante en el mismo checkout.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._merchant_store_apply_order_isolation_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._merchant_store_apply_order_isolation_vals(vals, records=self)
        res = super().write(vals)
        if 'merchant_id' in vals:
            self.mapped('order_line')._merchant_store_check_line_merchant()
        return res

    @api.model
    def _merchant_store_apply_order_isolation_vals(self, vals, records=None):
        """Align company and clear Tienda Apk origin when the order has a merchant."""
        if 'merchant_id' in vals:
            merchant_id = vals.get('merchant_id')
            if merchant_id:
                merchant = self.env['merchant_store.merchant'].browse(merchant_id)
                vals['company_id'] = merchant.company_id.id
                vals['order_bridge_origin'] = False
            return

        if records is None or not records:
            return

        merchant_orders = records.filtered('merchant_id')
        if not merchant_orders or merchant_orders != records:
            return

        vals['order_bridge_origin'] = False
        companies = merchant_orders.mapped('merchant_id.company_id')
        if len(companies) == 1:
            vals['company_id'] = companies.id

    @api.constrains('merchant_id', 'client_checkout_id', 'order_bridge_order_id')
    def _merchant_store_check_checkout_fields(self):
        for order in self:
            if order.client_checkout_id and not order.merchant_id:
                raise ValidationError(
                    _('El id. de checkout solo aplica a subórdenes de comerciantes.')
                )
            if order.order_bridge_order_id and not order.merchant_id:
                raise ValidationError(
                    _('El enlace a Tienda Apk solo aplica a subórdenes de comerciantes.')
                )
            linked = order.order_bridge_order_id
            if not linked:
                continue
            if linked.merchant_id:
                raise ValidationError(
                    _(
                        'El pedido %(name)s es una suborden y no puede enlazarse '
                        'como pedido de Tienda Apk.',
                        name=linked.display_name,
                    )
                )
            if linked.company_id != order.company_id:
                raise ValidationError(
                    _(
                        'El pedido %(name)s pertenece a otra compañía.',
                        name=linked.display_name,
                    )
                )
            if linked.order_bridge_origin not in ('app', 'admin'):
                raise ValidationError(
                    _(
                        'El pedido %(name)s no es un pedido de Tienda Apk.',
                        name=linked.display_name,
                    )
                )

    @api.constrains('client_checkout_id', 'partner_id', 'order_bridge_order_id', 'company_id')
    def _merchant_store_check_checkout_consistency(self):
        checkouts = {
            (order.company_id.id, order.client_checkout_id)
            for order in self
            if order.client_checkout_id and order.merchant_id
        }
        if not checkouts:
            return
        Order = self.env['sale.order']
        for company_id, checkout_id in checkouts:
            siblings = Order.search([
                ('company_id', '=', company_id),
                ('client_checkout_id', '=', checkout_id),
                ('merchant_id', '!=', False),
            ])
            partners = siblings.mapped('partner_id')
            if len(partners) > 1:
                raise ValidationError(
                    _(
                        'Las subórdenes del checkout %(checkout)s deben compartir el mismo cliente.',
                        checkout=checkout_id,
                    )
                )
            linked = siblings.mapped('order_bridge_order_id')
            if len(linked) > 1:
                raise ValidationError(
                    _(
                        'Las subórdenes del checkout %(checkout)s deben enlazar '
                        'el mismo pedido de Tienda Apk (o ninguno).',
                        checkout=checkout_id,
                    )
                )
            if linked and any(not order.order_bridge_order_id for order in siblings):
                raise ValidationError(
                    _(
                        'Las subórdenes del checkout %(checkout)s deben enlazar '
                        'el mismo pedido de Tienda Apk (o ninguno).',
                        checkout=checkout_id,
                    )
                )

    def _order_bridge_check_store_state_transition(self, old_ss, new_ss):
        self.ensure_one()
        if old_ss == new_ss:
            return
        if self.merchant_id:
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
            return
        return super()._order_bridge_check_store_state_transition(old_ss, new_ss)

    def _order_bridge_schedule_order_created_notification(self):
        """Send Telegram for merchant suborders created via checkout API."""
        self.ensure_one()
        if not self.merchant_id:
            return super()._order_bridge_schedule_order_created_notification()
        if not self.env.context.get('merchant_store_api_checkout'):
            return
        order_id = self.id
        dbname = self.env.cr.dbname

        @self.env.cr.postcommit.add
        def _send_merchant_order_created_telegram():
            with Registry(dbname).cursor() as cr:
                order = api.Environment(cr, SUPERUSER_ID, {})['sale.order'].browse(order_id).exists()
                if order and order.merchant_id:
                    text = format_merchant_order_created_message(order)
                    send_message(text, order_ref=order.name)

    def action_confirm(self):
        merchant_orders = self.filtered('merchant_id')
        if merchant_orders:
            raise UserError(
                _(
                    'No se puede confirmar la suborden %(name)s. '
                    'Las órdenes de comerciantes no se confirman en esta fase.',
                    name=merchant_orders[0].display_name,
                )
            )
        return super().action_confirm()

    @api.model
    def merchant_store_checkout(
        self,
        company,
        partner,
        client_checkout_id,
        lines,
        order_bridge_order=None,
    ):
        """Split merchant lines into one draft suborder per merchant (idempotent).

        ``lines`` is a sequence of dicts with ``product_id`` and ``qty``.
        If suborders for ``client_checkout_id`` already exist in ``company``, they
        are returned unchanged (first call wins).
        """
        company.ensure_one()
        partner.ensure_one()
        checkout_id = (client_checkout_id or '').strip()
        if not checkout_id:
            raise UserError(_('El id. de checkout es obligatorio.'))
        if not lines:
            raise UserError(_('El checkout no tiene líneas.'))

        existing = self.search([
            ('company_id', '=', company.id),
            ('client_checkout_id', '=', checkout_id),
            ('merchant_id', '!=', False),
        ])
        if existing:
            return existing

        linked = order_bridge_order
        if linked is not None and linked:
            linked.ensure_one()
            self._merchant_store_validate_linked_order(company, linked)
        else:
            linked = self.browse()

        by_merchant = self._merchant_store_group_checkout_lines(company, lines)
        Order = self.with_company(company).with_context(merchant_store_api_checkout=True)
        created = Order.browse()
        for merchant, merchant_lines in by_merchant.items():
            vals = {
                'partner_id': partner.id,
                'merchant_id': merchant.id,
                'company_id': company.id,
                'client_checkout_id': checkout_id,
                'order_line': [
                    Command.create({
                        'product_id': product.id,
                        'product_uom_qty': qty,
                    })
                    for product, qty in merchant_lines
                ],
            }
            if linked:
                vals['order_bridge_order_id'] = linked.id
            created |= Order.create(vals)
        return created

    @api.model
    def _merchant_store_validate_linked_order(self, company, linked):
        if linked.merchant_id:
            raise UserError(
                _(
                    'El pedido %(name)s es una suborden y no puede enlazarse '
                    'como pedido de Tienda Apk.',
                    name=linked.display_name,
                )
            )
        if linked.company_id != company:
            raise UserError(
                _(
                    'El pedido %(name)s pertenece a otra compañía.',
                    name=linked.display_name,
                )
            )
        if linked.order_bridge_origin not in ('app', 'admin'):
            raise UserError(
                _(
                    'El pedido %(name)s no es un pedido de Tienda Apk.',
                    name=linked.display_name,
                )
            )

    @api.model
    def _merchant_store_group_checkout_lines(self, company, lines):
        Product = self.env['product.product'].sudo()
        by_merchant = defaultdict(list)
        for line in lines:
            product_id = line.get('product_id') if isinstance(line, dict) else None
            qty = line.get('qty') if isinstance(line, dict) else None
            if not product_id or not qty:
                raise UserError(_('Cada línea del checkout necesita producto y cantidad.'))
            product = Product.browse(product_id).exists()
            if not product:
                raise UserError(
                    _('El producto %(product_id)s no existe.', product_id=product_id)
                )
            tmpl = product.product_tmpl_id
            merchant = tmpl.merchant_id
            if not merchant:
                raise UserError(
                    _(
                        'El producto %(product)s no pertenece a un comerciante.',
                        product=product.display_name,
                    )
                )
            if not merchant.active:
                raise UserError(
                    _(
                        'El comerciante %(merchant)s no está activo.',
                        merchant=merchant.display_name,
                    )
                )
            if tmpl.company_id and tmpl.company_id != company:
                raise UserError(
                    _(
                        'El producto %(product)s pertenece a otra compañía.',
                        product=product.display_name,
                    )
                )
            if merchant.company_id != company:
                raise UserError(
                    _(
                        'El producto %(product)s pertenece a otra compañía.',
                        product=product.display_name,
                    )
                )
            by_merchant[merchant].append((product, qty))
        return by_merchant


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.constrains('order_id', 'product_id')
    def _merchant_store_check_line_merchant(self):
        for line in self:
            if line.display_type or not line.product_id:
                continue
            order_merchant = line.order_id.merchant_id
            product_merchant = line.product_id.product_tmpl_id.merchant_id
            if order_merchant and product_merchant != order_merchant:
                raise ValidationError(
                    _(
                        'El producto %(product)s no pertenece al comerciante %(merchant)s '
                        'del pedido %(order)s.',
                        product=line.product_id.display_name,
                        merchant=order_merchant.display_name,
                        order=line.order_id.display_name,
                    )
                )
            if product_merchant and not order_merchant:
                raise ValidationError(
                    _(
                        'El producto %(product)s pertenece al comerciante %(merchant)s '
                        'y no puede entrar en un pedido sin comerciante.',
                        product=line.product_id.display_name,
                        merchant=product_merchant.display_name,
                    )
                )
