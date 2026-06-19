# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.http import request

from ..schemas import OrderCreateBody, OrdersListQuery
from ..schemas.responses import MessageErrorResponse, SimpleErrorResponse
from ..utils.concurrency import pg_advisory_xact_lock_device
from ..utils.decorators import (
    api_cors_preflight,
    api_device_auth,
    api_idempotent,
    api_json_response,
    api_validated_json_body,
    api_validated_query,
    catalog_context_for_partner,
    order_create_body_validation_context,
)
from ..utils.order_stock import get_order_bridge_warehouse
from ..utils.serialization import (
    order_cancel_response,
    orders_page_response,
    sale_order_to_created_response,
    sale_order_to_detail_response,
)


def _orders_create_idempotent_lookup(api_device, body, **_kwargs):
    return request.env['sale.order'].sudo().order_bridge_find_idempotent(
        api_device.sudo(), body,
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
    @api_validated_json_body(OrderCreateBody, validation_context=order_create_body_validation_context)
    @api_idempotent(
        lookup=_orders_create_idempotent_lookup,
        to_response=sale_order_to_created_response,
    )
    def orders_create(self, api_device=None, api_partner=None, body=None, **kwargs):
        partner = api_partner.sudo()
        device = api_device.sudo()
        pg_advisory_xact_lock_device(request.env.cr, device.id)
        Order = request.env['sale.order'].sudo()
        _catalog_company, product_domain = catalog_context_for_partner(partner)
        line_cmds, line_error = self._build_line_commands(body.lines, product_domain)
        if line_error:
            return line_error
        order_vals = {
            'partner_id': partner.id,
            'company_id': _catalog_company.id,
            'order_bridge_origin': 'app',
            'order_bridge_device_id': device.id,
            'order_line': line_cmds,
        }
        if body.client_order_id:
            order_vals['order_bridge_client_order_id'] = body.client_order_id
        warehouse = get_order_bridge_warehouse(request.env, _catalog_company)
        if warehouse:
            order_vals['warehouse_id'] = warehouse.id
        try:
            with request.env.cr.savepoint():
                order = Order.create(order_vals)
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
                        message=f'el producto {line.product_id} no está disponible',
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
                    message='no se puede cancelar este pedido en su estado actual',
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
