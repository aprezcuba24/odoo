# Part of Odoo. See LICENSE file for full copyright and licensing details.

import functools
import json
import logging
from datetime import timedelta

from pydantic import BaseModel, ValidationError

from odoo import fields
from odoo.http import request

from ..schemas.errors import pydantic_errors_to_api_body
from ..schemas.responses import (
    SimpleErrorResponse,
    UnauthorizedErrorResponse,
    ValidationErrorResponse,
)

_logger = logging.getLogger(__name__)

_LAST_ACTIVITY_WRITE_INTERVAL = timedelta(seconds=60)

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
    raw = request.httprequest.get_data(cache=True, as_text=True) or ''
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
    """Return (catalog_company, product_domain).

    ``partner`` may be falsy for anonymous catalog (uses request env company).
    """
    Company = request.env['res.company'].sudo()
    catalog_company = Company._order_bridge_catalog_company_for_partner(
        partner, request.env.company.sudo()
    )
    product_domain = catalog_company._order_bridge_product_domain()
    return catalog_company, product_domain


def _order_bridge_request_context(
    kwargs,
    *,
    require_device=True,
    inject_catalog_domain=False,
):
    """CORS preflight, resolve device, optional catalog company/domain into ``kwargs``.

    Returns a werkzeug response to return immediately, or ``None`` if the handler
    should run.
    """
    if request.httprequest.method == 'OPTIONS':
        return api_cors_preflight()
    device = resolve_api_device()
    if not device:
        if require_device:
            return api_json_response(
                UnauthorizedErrorResponse(
                    error='unauthorized',
                    message='Clave de dispositivo no válida o ausente',
                ),
                401,
            )
        kwargs['api_device'] = None
        kwargs['api_partner'] = None
        partner = None
    else:
        now = fields.Datetime.now()
        if not device.last_activity or (now - device.last_activity) > _LAST_ACTIVITY_WRITE_INTERVAL:
            device.sudo().write({'last_activity': now})
        kwargs['api_device'] = device
        kwargs['api_partner'] = device.partner_id
        partner = device.partner_id
    if inject_catalog_domain:
        catalog_company, product_domain = catalog_context_for_partner(partner)
        kwargs['catalog_company'] = catalog_company
        kwargs['product_domain'] = product_domain
    return None


def api_device_auth(_func=None, *, inject_catalog_domain=False):
    """Require a valid active device; inject api_device and api_partner.

    With inject_catalog_domain=True, also inject catalog_company and product_domain.
    """

    def decorator(endpoint):
        @functools.wraps(endpoint)
        def wrapper(self, *args, **kwargs):
            early = _order_bridge_request_context(
                kwargs,
                require_device=True,
                inject_catalog_domain=inject_catalog_domain,
            )
            if early is not None:
                return early
            return endpoint(self, *args, **kwargs)

        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator


def api_access(endpoint):
    """Inject catalog company/domain; Bearer device key optional.

    Without a valid device key, the catalog uses ``request.env.company`` (same as
    anonymous public website). With a valid key, ``last_activity`` is updated and
    the partner's company is used when set.
    """

    @functools.wraps(endpoint)
    def wrapper(self, *args, **kwargs):
        early = _order_bridge_request_context(
            kwargs,
            require_device=False,
            inject_catalog_domain=True,
        )
        if early is not None:
            return early
        return endpoint(self, *args, **kwargs)

    return wrapper


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
