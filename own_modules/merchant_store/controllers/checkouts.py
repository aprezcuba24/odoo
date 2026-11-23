# Part of Odoo. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.order_bridge.schemas.responses import MessageErrorResponse, SimpleErrorResponse
from odoo.addons.order_bridge.utils.concurrency import pg_advisory_xact_lock_device
from odoo.addons.order_bridge.utils.decorators import (
    api_device_auth,
    api_json_response,
    api_validated_json_body,
)

from ..schemas import CheckoutCreateBody
from ..utils.catalog import merchant_store_product_domain
from ..utils.decorators import api_merchant_store_enabled
from ..utils.serialization import checkout_created_response


class MerchantStoreCheckoutsController(http.Controller):
    @http.route(
        '/api/merchant_store/checkouts',
        type='http',
        auth='public',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    @api_device_auth
    @api_merchant_store_enabled
    @api_validated_json_body(CheckoutCreateBody)
    def checkouts_create(self, api_device=None, api_partner=None, body=None, **kwargs):
        device = api_device.sudo()
        partner = api_partner.sudo()
        company = device.company_id
        checkout_id = body.client_checkout_id
        Order = request.env['sale.order'].sudo()

        existing = Order.search([
            ('company_id', '=', company.id),
            ('client_checkout_id', '=', checkout_id),
            ('merchant_id', '!=', False),
        ])
        if existing:
            if existing.partner_id != partner:
                return api_json_response(
                    MessageErrorResponse(
                        error='validation',
                        message=(
                            f'El checkout {checkout_id} pertenece a otro cliente.'
                        ),
                    ),
                    400,
                )
            return api_json_response(checkout_created_response(existing, checkout_id))

        product_domain = merchant_store_product_domain(company)
        Product = request.env['product.product'].sudo()
        lines = []
        for line in body.lines:
            product = Product.browse(line.product_id).exists()
            if not product or not product.filtered_domain(product_domain):
                return api_json_response(
                    MessageErrorResponse(
                        error='validation',
                        message=f'el producto {line.product_id} no está disponible',
                    ),
                    400,
                )
            lines.append({'product_id': product.id, 'qty': line.qty})

        linked = None
        if body.order_bridge_order_id:
            linked = Order.browse(body.order_bridge_order_id).exists()
            if not linked:
                return api_json_response(
                    MessageErrorResponse(
                        error='validation',
                        message=(
                            f'el pedido de Tienda Apk {body.order_bridge_order_id} '
                            'no existe'
                        ),
                    ),
                    400,
                )

        pg_advisory_xact_lock_device(request.env.cr, device.id)
        try:
            with request.env.cr.savepoint():
                orders = Order.with_company(company).merchant_store_checkout(
                    company,
                    partner,
                    checkout_id,
                    lines,
                    order_bridge_order=linked,
                )
        except (UserError, ValidationError) as e:
            return api_json_response(
                MessageErrorResponse(error='validation', message=str(e)),
                400,
            )
        except IntegrityError:
            existing = Order.search([
                ('company_id', '=', company.id),
                ('client_checkout_id', '=', checkout_id),
                ('merchant_id', '!=', False),
            ])
            if existing and existing.partner_id == partner:
                return api_json_response(
                    checkout_created_response(existing, checkout_id),
                )
            return api_json_response(SimpleErrorResponse(error='conflict'), 409)

        return api_json_response(checkout_created_response(orders, checkout_id))
