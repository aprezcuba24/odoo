# Part of Odoo. See LICENSE file for full copyright and licensing details.

import functools
import json
import logging

from pydantic import BaseModel, ValidationError

from odoo import fields
from odoo.http import request

from ..schemas.errors import pydantic_errors_to_api_body
from ..schemas.responses import (
    ConfigurationErrorResponse,
    SimpleErrorResponse,
    UnauthorizedErrorResponse,
    ValidationErrorResponse,
)

_logger = logging.getLogger(__name__)

CORS_HEADERS = [
    ('Access-Control-Allow-Origin', '*'),
    ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
    ('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, OPTIONS'),
    ('Access-Control-Max-Age', '86400'),
]


def api_json_response(payload, status=200):
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode='json')
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
    """Return (pos_config, catalog_company, product_domain).

    pos_config is False when the catalog company has no order bridge POS linked.
    """
    Company = request.env['res.company'].sudo()
    catalog_company = Company._order_bridge_catalog_company_for_partner(
        partner, request.env.company.sudo()
    )
    pos_config = catalog_company._order_bridge_pos_config()
    product_domain = catalog_company._order_bridge_product_domain()
    return pos_config, catalog_company, product_domain


_POS_CONFIG_ERROR = ConfigurationErrorResponse(
    error='configuration',
    message='No point of sale is linked for the order bridge. Configure it on the company or in Settings.',
)


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
                return api_json_response(
                    UnauthorizedErrorResponse(
                        error='unauthorized',
                        message='Invalid or missing device key',
                    ),
                    401,
                )
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


def api_validated_query(model_cls, *, kwarg_name='q'):
    """Parse and validate GET query params; inject model instance as ``kwarg_name``."""

    def decorator(endpoint):
        @functools.wraps(endpoint)
        def wrapper(self, *args, **kwargs):
            try:
                parsed = model_cls.from_request_params(request.params)
            except ValidationError as e:
                body = pydantic_errors_to_api_body(e)
                return api_json_response(ValidationErrorResponse.model_validate(body), 400)
            kwargs[kwarg_name] = parsed
            return endpoint(self, *args, **kwargs)

        return wrapper

    return decorator


def api_validated_json_body(model_cls, *, kwarg_name='body'):
    """Parse JSON body and validate with Pydantic; inject model as ``kwarg_name``.

    Returns 400 for invalid JSON or validation errors. For OPTIONS requests,
    returns CORS preflight without calling the handler (for routes without
    ``api_device_auth``).
    """

    def decorator(endpoint):
        @functools.wraps(endpoint)
        def wrapper(self, *args, **kwargs):
            if request.httprequest.method == 'OPTIONS':
                return api_cors_preflight()
            body = get_json_body()
            if body is None:
                return api_json_response(SimpleErrorResponse(error='invalid_json'), 400)
            try:
                parsed = model_cls.model_validate(body)
            except ValidationError as e:
                err = pydantic_errors_to_api_body(e)
                return api_json_response(ValidationErrorResponse.model_validate(err), 400)
            kwargs[kwarg_name] = parsed
            return endpoint(self, *args, **kwargs)

        return wrapper

    return decorator
