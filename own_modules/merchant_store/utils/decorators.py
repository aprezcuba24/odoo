# Part of Odoo. See LICENSE file for full copyright and licensing details.

import functools

from odoo.addons.order_bridge.schemas.responses import SimpleErrorResponse
from odoo.addons.order_bridge.utils.decorators import api_json_response

from .catalog import merchant_store_app_enabled


def api_merchant_store_enabled(endpoint):
    """Return 404 when company_onboarding has Comercios off for the device company."""

    @functools.wraps(endpoint)
    def wrapper(self, *args, **kwargs):
        device = kwargs.get('api_device')
        company = device.sudo().company_id if device else None
        if company is not None and not merchant_store_app_enabled(company):
            return api_json_response(SimpleErrorResponse(error='not_found'), 404)
        return endpoint(self, *args, **kwargs)

    return wrapper
