# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.http import request

from .decorators import (
    mobile_catalog_context,
    get_json_body,
    mobile_auth,
    mobile_cors_preflight,
    mobile_json_response,
)


class MobileOrdersController(http.Controller):
    @http.route('/api/mobile/orders', type='http', auth='public', methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    @mobile_auth
    def mobile_orders(self, mobile_device=None, mobile_partner=None, **kwargs):
        partner = mobile_partner.sudo()
        if request.httprequest.method == 'GET':
            limit = min(int(request.params.get('limit') or 50), 200)
            offset = int(request.params.get('offset') or 0)
            state = request.params.get('state')
            domain = [
                ('partner_id', '=', partner.id),
                ('mobile_origin', 'in', ['app', 'admin']),
            ]
            if state:
                domain.append(('state', '=', state))
            Order = request.env['sale.order'].sudo()
            orders = Order.search(domain, limit=limit, offset=offset, order='date_order desc, id desc')
            total = Order.search_count(domain)
            return mobile_json_response({
                'items': [self._order_to_dict(o) for o in orders],
                'total': total,
                'limit': limit,
                'offset': offset,
            })
        body = get_json_body()
        if body is None:
            return mobile_json_response({'error': 'invalid_json'}, 400)
        lines = body.get('lines') or []
        if not lines:
            return mobile_json_response({'error': 'validation', 'message': 'lines required'}, 400)
        pos_config, _catalog_company, product_domain = mobile_catalog_context(partner)
        if not pos_config:
            return mobile_json_response(
                {
                    'error': 'configuration',
                    'message': 'No point of sale is linked for the mobile app. Configure it on the company or in Settings.',
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
                return mobile_json_response({'error': 'validation', 'message': 'invalid qty'}, 400)
            if not pid or qty <= 0:
                return mobile_json_response({'error': 'validation', 'message': 'invalid line'}, 400)
            product = Product.browse(int(pid)).exists()
            if not product or not product.filtered_domain(product_domain):
                return mobile_json_response({'error': 'validation', 'message': f'product {pid} not available'}, 400)
            line_cmds.append(Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
            }))
        try:
            order = request.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'company_id': pos_config.company_id.id,
                'mobile_origin': 'app',
                'mobile_device_id': mobile_device.id,
                'mobile_pos_config_id': pos_config.id,
                'order_line': line_cmds,
            })
        except UserError as e:
            return mobile_json_response({'error': 'validation', 'message': str(e)}, 400)
        return mobile_json_response({
            'id': order.id,
            'name': order.name,
            'mobile_order_ref': order.mobile_order_ref,
            'state': order.state,
            'device_validated': order.mobile_device_validated,
        })

    @http.route('/api/mobile/orders/<int:order_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @mobile_auth
    def mobile_order_detail(self, order_id, mobile_device=None, mobile_partner=None, **kwargs):
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.id != mobile_partner.id or order.mobile_origin not in ('app', 'admin'):
            return mobile_json_response({'error': 'not_found'}, 404)
        return mobile_json_response(self._order_to_dict(order, lines=True))

    @http.route(
        '/api/mobile/orders/<int:order_id>/cancel',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    @mobile_auth
    def mobile_order_cancel(self, order_id, mobile_device=None, mobile_partner=None, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return mobile_cors_preflight()
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.id != mobile_partner.id or order.mobile_origin not in ('app', 'admin'):
            return mobile_json_response({'error': 'not_found'}, 404)
        if order.state != 'draft':
            return mobile_json_response({'error': 'forbidden', 'message': 'only draft orders can be cancelled'}, 400)
        try:
            order.action_cancel()
        except UserError as e:
            return mobile_json_response({'error': 'validation', 'message': str(e)}, 400)
        return mobile_json_response({'id': order.id, 'state': order.state})

    def _order_to_dict(self, order, lines=False):
        base = {
            'id': order.id,
            'name': order.name,
            'mobile_order_ref': order.mobile_order_ref,
            'mobile_origin': order.mobile_origin,
            'state': order.state,
            'date_order': order.date_order.isoformat() if order.date_order else None,
            'amount_total': order.amount_total,
            'currency': order.currency_id.name if order.currency_id else None,
            'device_validated': order.mobile_device_validated,
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
