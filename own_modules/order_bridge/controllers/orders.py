# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.http import request

from ..schemas import OrderCreateBody, OrdersListQuery
from ..schemas.responses import MessageErrorResponse, SimpleErrorResponse
from ..utils.decorators import (
    _POS_CONFIG_ERROR,
    api_cors_preflight,
    api_device_auth,
    api_json_response,
    api_validated_json_body,
    api_validated_query,
    catalog_context_for_partner,
)
from ..utils.serialization import (
    order_cancel_response,
    orders_page_response,
    sale_order_to_created_response,
    sale_order_to_detail_response,
)


class OrdersController(http.Controller):
    @http.route('/api/order_bridge/orders', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    @api_validated_query(OrdersListQuery)
    def orders(self, api_device=None, api_partner=None, q=None, **kwargs):
        partner = api_partner.sudo()
        limit = q.limit
        offset = q.offset
        state = q.state
        domain = [
            ('partner_id', '=', partner.id),
            ('order_bridge_origin', 'in', ['app', 'admin']),
        ]
        if state:
            domain.append(('state', '=', state))
        Order = request.env['sale.order'].sudo()
        orders = Order.search(domain, limit=limit, offset=offset, order='date_order desc, id desc')
        total = Order.search_count(domain)
        return api_json_response(orders_page_response(orders, limit, offset, total))

    @http.route('/api/order_bridge/orders', type='http', auth='public', methods=['POST'], csrf=False)
    @api_device_auth
    @api_validated_json_body(OrderCreateBody)
    def orders_create(self, api_device=None, api_partner=None, body=None, **kwargs):
        partner = api_partner.sudo()
        pos_config, _catalog_company, product_domain = catalog_context_for_partner(partner)
        if not pos_config:
            return api_json_response(_POS_CONFIG_ERROR, status=503)
        line_cmds, line_error = self._build_line_commands(body.lines, product_domain)
        if line_error:
            return line_error
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
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(e)),
                400,
            )
        return api_json_response(sale_order_to_created_response(order))

    def _build_line_commands(self, lines, product_domain):
        line_cmds = []
        Product = request.env['product.product'].sudo()
        for line in lines:
            product = Product.browse(line.product_id).exists()
            if not product or not product.filtered_domain(product_domain):
                return None, api_json_response(
                    MessageErrorResponse(
                        error='validation',
                        message=f'product {line.product_id} not available',
                    ),
                    400,
                )
            line_cmds.append(Command.create({
                'product_id': product.id,
                'product_uom_qty': line.qty,
            }))
        return line_cmds, None

    def _retrieve_order(self, order_id, api_partner):
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or order.partner_id.id != api_partner.id or order.order_bridge_origin not in ('app', 'admin'):
            return None, api_json_response(SimpleErrorResponse(error='not_found'), 404)
        return order, None

    @http.route('/api/order_bridge/orders/<int:order_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    @api_device_auth
    def order_detail(self, order_id, api_partner=None, **kwargs):
        order, error = self._retrieve_order(order_id, api_partner)
        if error:
            return error
        return api_json_response(sale_order_to_detail_response(order))

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
            return api_json_response(
                MessageErrorResponse(
                    error='forbidden',
                    message='only draft orders can be cancelled',
                ),
                400,
            )
        try:
            order.action_cancel()
        except UserError as e:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(e)),
                400,
            )
        return api_json_response(order_cancel_response(order))
