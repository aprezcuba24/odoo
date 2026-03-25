# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.http import request

from .decorators import (
    api_cors_preflight,
    api_device_auth,
    api_json_response,
    catalog_context_for_partner,
    get_json_body,
)


class OrdersController(http.Controller):
    @http.route('/api/order_bridge/orders', type='http', auth='public', methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    @api_device_auth
    def orders(self, api_device=None, api_partner=None, **kwargs):
        partner = api_partner.sudo()
        if request.httprequest.method == 'GET':
            limit = min(int(request.params.get('limit') or 50), 200)
            offset = int(request.params.get('offset') or 0)
            state = request.params.get('state')
            domain = [
                ('partner_id', '=', partner.id),
                ('order_bridge_origin', 'in', ['app', 'admin']),
            ]
            if state:
                domain.append(('state', '=', state))
            Order = request.env['sale.order'].sudo()
            orders = Order.search(domain, limit=limit, offset=offset, order='date_order desc, id desc')
            total = Order.search_count(domain)
            return api_json_response({
                'items': [self._order_to_dict(o) for o in orders],
                'total': total,
                'limit': limit,
                'offset': offset,
            })
        body = get_json_body()
        if body is None:
            return api_json_response({'error': 'invalid_json'}, 400)
        lines = body.get('lines') or []
        if not lines:
            return api_json_response({'error': 'validation', 'message': 'lines required'}, 400)
        pos_config, _catalog_company, product_domain = catalog_context_for_partner(partner)
        if not pos_config:
            return api_json_response(
                {
                    'error': 'configuration',
                    'message': 'No point of sale is linked for the order bridge. Configure it on the company or in Settings.',
                },
                503,
            )
        line_cmds = []
        Product = request.env['product.product'].sudo()
        for line in lines:
            pid = line.get('product_id')
            qty = line.get('qty') or line.get('product_uom_qty') or 0
            try:
                qty = float(qty)
            except (TypeError, ValueError):
                return api_json_response({'error': 'validation', 'message': 'invalid qty'}, 400)
            if not pid or qty <= 0:
                return api_json_response({'error': 'validation', 'message': 'invalid line'}, 400)
            product = Product.browse(int(pid)).exists()
            if not product or not product.filtered_domain(product_domain):
                return api_json_response({'error': 'validation', 'message': f'product {pid} not available'}, 400)
            line_cmds.append(Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
            }))
        try:
            order = request.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'company_id': pos_config.company_id.id,
                'order_bridge_origin': 'app',
                'order_bridge_device_id': api_device.id,
                'order_bridge_pos_config_id': pos_config.id,
                'order_line': line_cmds,
            })
        except UserError as e:
            return api_json_response({'error': 'validation', 'message': str(e)}, 400)
        return api_json_response({
            'id': order.id,
            'name': order.name,
            'order_ref': order.order_bridge_ref,
            'state': order.state,
            'device_validated': order.order_bridge_device_validated,
        })

    @http.route('/api/order_bridge/orders/<int:order_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    def order_detail(self, order_id, api_device=None, api_partner=None, **kwargs):
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.id != api_partner.id or order.order_bridge_origin not in ('app', 'admin'):
            return api_json_response({'error': 'not_found'}, 404)
        return api_json_response(self._order_to_dict(order, lines=True))

    @http.route(
        '/api/order_bridge/orders/<int:order_id>/cancel',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    def order_cancel(self, order_id, api_device=None, api_partner=None, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.id != api_partner.id or order.order_bridge_origin not in ('app', 'admin'):
            return api_json_response({'error': 'not_found'}, 404)
        if order.state != 'draft':
            return api_json_response({'error': 'forbidden', 'message': 'only draft orders can be cancelled'}, 400)
        try:
            order.action_cancel()
        except UserError as e:
            return api_json_response({'error': 'validation', 'message': str(e)}, 400)
        return api_json_response({'id': order.id, 'state': order.state})

    def _order_to_dict(self, order, lines=False):
        base = {
            'id': order.id,
            'name': order.name,
            'order_ref': order.order_bridge_ref,
            'origin': order.order_bridge_origin,
            'state': order.state,
            'date_order': order.date_order.isoformat() if order.date_order else None,
            'amount_total': order.amount_total,
            'currency': order.currency_id.name if order.currency_id else None,
            'device_validated': order.order_bridge_device_validated,
        }
        if lines:
            base['lines'] = [{
                'product_id': l.product_id.id,
                'name': l.name,
                'qty': l.product_uom_qty,
                'price_unit': l.price_unit,
                'price_subtotal': l.price_subtotal,
            } for l in order.order_line if not l.display_type]
        return base
