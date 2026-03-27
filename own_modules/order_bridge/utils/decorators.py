# Part of Odoo. See LICENSE file for full copyright and licensing details.

import functools
import json
import logging

from odoo import fields
from odoo.http import request

_logger = logging.getLogger(__name__)

CORS_HEADERS = [
    ('Access-Control-Allow-Origin', '*'),
    ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
    ('Access-Control-Max-Age', '86400'),
]


def api_json_response(payload, status=200):
    return request.make_json_response(
        payload,
        status=status,
        headers=[('Content-Type', 'application/json; charset=utf-8'), *CORS_HEADERS],
    )


def api_cors_preflight():
    return request.make_response('', status=204, headers=list(CORS_HEADERS))


def get_bearer_device_key():
    auth = request.httprequest.headers.get('Authorization', '') or ''
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return None


def get_json_body():
    raw = request.httprequest.get_data(cache=False, as_text=True) or ''
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        _logger.warning('Invalid JSON body')
        return None


def resolve_api_device():
    key = get_bearer_device_key()
    if not key:
        return None
    device = request.env['order_bridge.device'].sudo().search(
        [('device_key', '=', key), ('active', '=', True)],
        limit=1,
    )
    return device


def catalog_context_for_partner(partner):
    """Return (pos_config, catalog_company, product_domain) or (None, company, None) if POS not linked."""
    Company = request.env['res.company'].sudo()
    catalog_company = Company._order_bridge_catalog_company_for_partner(
        partner, request.env.company.sudo()
    )
    product_domain = catalog_company._order_bridge_product_domain()
    return product_domain


_POS_CONFIG_ERROR = {
    'error': 'configuration',
    'message': 'No point of sale is linked for the order bridge. Configure it on the company or in Settings.',
}


def api_device_auth(_func=None, *, require_pos_config=False):
    """Require a valid active device; inject api_device and api_partner.

    With require_pos_config=True, also require a linked POS for the catalog company
    and inject pos_config, catalog_company, product_domain.
    """

    def decorator(endpoint):
        @functools.wraps(endpoint)
        def wrapper(self, *args, **kwargs):
            if request.httprequest.method == 'OPTIONS':
                return api_cors_preflight()
            device = resolve_api_device()
            if not device:
                return api_json_response({'error': 'unauthorized', 'message': 'Invalid or missing device key'}, 401)
            device.sudo().write({'last_activity': fields.Datetime.now()})
            kwargs['api_device'] = device
            kwargs['api_partner'] = device.partner_id
            if require_pos_config:
                pos_config, catalog_company, product_domain = catalog_context_for_partner(device.partner_id)
                if not pos_config:
                    return api_json_response(_POS_CONFIG_ERROR, status=503)
                kwargs['pos_config'] = pos_config
                kwargs['catalog_company'] = catalog_company
                kwargs['product_domain'] = product_domain
            return endpoint(self, *args, **kwargs)

        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator
