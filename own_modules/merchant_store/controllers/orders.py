# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

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
    purchase_row_response,
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

        own_domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('merchant_id', '=', False),
            ('order_bridge_origin', 'in', ['app', 'admin']),
        ]
        sub_domain = self._order_domain(company, partner)

        own_rows = Order.search_read(
            own_domain,
            ['id', 'date_order'],
            order='date_order desc, id desc',
        )
        sub_rows = Order.search_read(
            sub_domain,
            ['id', 'date_order', 'client_checkout_id', 'order_bridge_order_id'],
            order='date_order asc, id asc',
        )

        groups = {}
        for row in own_rows:
            key = f"order:{row['id']}"
            groups[key] = {
                'purchase_key': key,
                'order_id': row['id'],
                'suborder_ids': [],
                'client_checkout_id': None,
                'date_order': row['date_order'],
                'sort_id': row['id'],
            }

        for srow in sub_rows:
            linked = srow['order_bridge_order_id']
            linked_id = linked[0] if linked else None
            checkout_id = srow['client_checkout_id'] or None
            if linked_id and f'order:{linked_id}' in groups:
                group = groups[f'order:{linked_id}']
                group['suborder_ids'].append(srow['id'])
                if checkout_id and not group['client_checkout_id']:
                    group['client_checkout_id'] = checkout_id
            elif checkout_id:
                key = f'checkout:{checkout_id}'
                if key not in groups:
                    groups[key] = {
                        'purchase_key': key,
                        'order_id': None,
                        'suborder_ids': [],
                        'client_checkout_id': checkout_id,
                        'date_order': srow['date_order'],
                        'sort_id': srow['id'],
                    }
                groups[key]['suborder_ids'].append(srow['id'])
            else:
                key = f"suborder:{srow['id']}"
                groups[key] = {
                    'purchase_key': key,
                    'order_id': None,
                    'suborder_ids': [srow['id']],
                    'client_checkout_id': None,
                    'date_order': srow['date_order'],
                    'sort_id': srow['id'],
                }

        ordered_groups = sorted(
            groups.values(),
            key=lambda g: (g['date_order'] or datetime.min, g['sort_id']),
            reverse=True,
        )
        total = len(ordered_groups)
        page_groups = ordered_groups[q.offset : q.offset + q.limit]

        needed_ids = []
        for g in page_groups:
            if g['order_id']:
                needed_ids.append(g['order_id'])
            needed_ids.extend(g['suborder_ids'])

        orders_by_id = {o.id: o for o in Order.browse(needed_ids)} if needed_ids else {}
        items = [
            purchase_row_response(
                purchase_key=g['purchase_key'],
                client_checkout_id=g['client_checkout_id'],
                date_order=g['date_order'],
                own_order=orders_by_id.get(g['order_id']) if g['order_id'] else None,
                suborders=[orders_by_id[sid] for sid in g['suborder_ids'] if sid in orders_by_id],
            )
            for g in page_groups
        ]
        return api_json_response(purchases_page_response(items, q.limit, q.offset, total))
