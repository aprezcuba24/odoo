# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _mcp_api_normalize_lines(self, lines):
        """Validate MCP line payloads: [{product_id, qty|product_uom_qty}, ...]."""
        if not lines:
            raise ValidationError(_('Se requiere al menos una línea de pedido.'))
        if not isinstance(lines, list):
            raise ValidationError(_('lines debe ser una lista.'))

        normalized = []
        Product = self.env['product.product']
        precision = self.env['decimal.precision'].precision_get('Product Unit')
        for index, line in enumerate(lines):
            if not isinstance(line, dict):
                raise ValidationError(_('La línea %(idx)s no es un objeto.', idx=index + 1))
            product_id = line.get('product_id')
            if not product_id:
                raise ValidationError(_('La línea %(idx)s requiere product_id.', idx=index + 1))
            qty = line.get('product_uom_qty', line.get('qty'))
            if qty is None:
                raise ValidationError(
                    _('La línea %(idx)s requiere qty o product_uom_qty.', idx=index + 1),
                )
            if float_compare(qty, 0.0, precision_digits=precision) <= 0:
                raise ValidationError(_('La cantidad de la línea %(idx)s debe ser positiva.', idx=index + 1))

            product = Product.browse(int(product_id)).exists()
            if not product:
                raise ValidationError(_('Producto %(pid)s no encontrado.', pid=product_id))
            if not product.sale_ok:
                raise UserError(
                    _('El producto %(name)s no está disponible para ventas.', name=product.display_name),
                )
            normalized.append({
                'product_id': product.id,
                'product_uom_qty': qty,
            })
        return normalized

    @api.model
    def _mcp_api_order_response(self, order):
        return {
            'id': order.id,
            'name': order.name,
            'state': order.state,
            'amount_total': order.amount_total,
            'partner_id': order.partner_id.id,
            'client_order_ref': order.client_order_ref or False,
        }

    @api.model
    def api_create_confirmed_order(self, partner_id, lines, client_order_ref=None):
        """Create and confirm a Tienda Apk admin order (JSON-2 / MCP).

        Sets ``order_bridge_origin='admin'`` and delegates to ``order_bridge``'s
        ``create`` hooks (reference, address snapshot, auto-confirm, greedy
        stock reservation). Runs as ``self.env.user``; ACL and record rules apply.

        :param int partner_id: Customer ``res.partner`` id.
        :param list lines: ``[{product_id, qty}]`` or ``product_uom_qty`` per line.
        :param str client_order_ref: Optional customer reference on the order.
        :returns: dict with id, name, state, amount_total, partner_id, client_order_ref
        """
        partner = self.env['res.partner'].browse(int(partner_id)).exists()
        if not partner:
            raise ValidationError(_('Cliente %(pid)s no encontrado.', pid=partner_id))

        line_vals = self._mcp_api_normalize_lines(lines)
        order_line = [(0, 0, vals) for vals in line_vals]
        vals = {
            'partner_id': partner.id,
            'order_bridge_origin': 'admin',
            'order_line': order_line,
        }
        if client_order_ref:
            vals['client_order_ref'] = client_order_ref

        order = self.create(vals)
        return self._mcp_api_order_response(order)
