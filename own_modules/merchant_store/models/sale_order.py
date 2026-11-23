# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.order_bridge.utils.constant import ORDER_BRIDGE_ALLOWED_STORE_TRANSITIONS


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    merchant_id = fields.Many2one(
        'merchant_store.merchant',
        string='Comerciante',
        ondelete='restrict',
        index=True,
        check_company=True,
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
