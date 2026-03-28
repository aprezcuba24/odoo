# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.http import request

from ..utils.decorators import (
    _POS_CONFIG_ERROR,
    api_cors_preflight,
    api_device_auth,
    api_json_response,
    catalog_context_for_partner,
    get_json_body,
)
from ..utils.serialization import (
    sale_order_created_to_api_dict,
    sale_order_to_api_dict,
    serialize_many,
    serialize_one,
    serialize_pagination,
)


class OrdersController(http.Controller):
    @http.route('/api/order_bridge/orders', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    def orders(self, api_device=None, api_partner=None, **kwargs):
        partner = api_partner.sudo()
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
        items = serialize_many(orders, sale_order_to_api_dict)
        return api_json_response(serialize_pagination(items, limit, offset, total))

    @http.route('/api/order_bridge/orders', type='http', auth='public', methods=['POST'], csrf=False)
    def orders_create(self, partner, api_device, pos_config=None, **kwargs):
        body = get_json_body()
        if body is None:
            return api_json_response({'error': 'invalid_json'}, 400)
        lines = body.get('lines') or []
        if not lines:
            return api_json_response({'error': 'validation', 'message': 'lines required'}, 400)
        pos_config, _catalog_company, product_domain = catalog_context_for_partner(partner)
        if not pos_config:
            return api_json_response(_POS_CONFIG_ERROR, status=503)
        line_cmds = self._validate_lines(lines, product_domain)
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
        return api_json_response(serialize_one(order, sale_order_created_to_api_dict))

    def _validate_lines(self, lines, product_domain):
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
        return line_cmds

    def _retrieve_order(self, order_id, api_partner):
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.id != api_partner.id or order.order_bridge_origin not in ('app', 'admin'):
            return None, api_json_response({'error': 'not_found'}, 404)
        return order, None

    @http.route('/api/order_bridge/orders/<int:order_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    def order_detail(self, order_id, api_partner=None, **kwargs):
        order, error = self._retrieve_order(order_id, api_partner)
        if error:
            return error
        return api_json_response(serialize_one(order, sale_order_to_api_dict, lines=True))

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
        order, error = self._retrieve_order(order_id, api_partner)
        if error:
            return error
        if order.state != 'draft':
            return api_json_response({'error': 'forbidden', 'message': 'only draft orders can be cancelled'}, 400)
        try:
            order.action_cancel()
        except UserError as e:
            return api_json_response({'error': 'validation', 'message': str(e)}, 400)
        return api_json_response({'id': order.id, 'state': order.state})
