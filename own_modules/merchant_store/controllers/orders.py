# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.order_bridge.schemas.responses import SimpleErrorResponse
from odoo.addons.order_bridge.utils.decorators import (
    api_device_auth,
    api_json_response,
    api_validated_query,
)

from ..schemas import OrdersListQuery, PurchasesListQuery
from ..utils.decorators import api_merchant_store_enabled
from ..utils.serialization import (
    orders_page_response,
    purchases_page_response,
    sale_order_to_detail_response,
)


class MerchantStoreOrdersController(http.Controller):
    def _order_domain(self, company, partner):
        return [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('merchant_id', '!=', False),
        ]

    def _retrieve_order(self, order_id, company, partner):
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if (
            not order
            or order.company_id != company
            or order.partner_id != partner
            or not order.merchant_id
        ):
            return None, api_json_response(SimpleErrorResponse(error='not_found'), 404)
        return order, None

    @http.route(
        '/api/merchant_store/orders',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_merchant_store_enabled
    @api_validated_query(OrdersListQuery)
    def orders(self, api_device=None, api_partner=None, q=None, **kwargs):
        company = api_device.sudo().company_id
        partner = api_partner.sudo()
        domain = self._order_domain(company, partner)
        if q.store_state:
            domain.append(('order_bridge_store_state', '=', q.store_state))
        Order = request.env['sale.order'].sudo()
        total = Order.search_count(domain)
        orders = Order.search(
            domain,
            limit=q.limit,
            offset=q.offset,
            order='date_order desc, id desc',
        )
        return api_json_response(orders_page_response(orders, q.limit, q.offset, total))

    @http.route(
        '/api/merchant_store/orders/<int:order_id>',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_merchant_store_enabled
    def order_detail(self, order_id, api_device=None, api_partner=None, **kwargs):
        company = api_device.sudo().company_id
        partner = api_partner.sudo()
        order, error = self._retrieve_order(order_id, company, partner)
        if error:
            return error
        return api_json_response(sale_order_to_detail_response(order))

    @http.route(
        '/api/merchant_store/purchases',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_merchant_store_enabled
    @api_validated_query(PurchasesListQuery)
    def purchases(self, api_device=None, api_partner=None, q=None, **kwargs):
        company = api_device.sudo().company_id
        partner = api_partner.sudo()
        Order = request.env['sale.order'].sudo()

        domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            '|',
            ('merchant_id', '!=', False),
            '&',
            ('merchant_id', '=', False),
            ('order_bridge_origin', 'in', ['app', 'admin']),
        ]
        total = Order.search_count(domain)
        orders = Order.search(
            domain,
            limit=q.limit,
            offset=q.offset,
            order='date_order desc, id desc',
        )
        return api_json_response(purchases_page_response(orders, q.limit, q.offset, total))
