# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.order_bridge.utils.decorators import CORS_HEADERS, api_cors_preflight
from odoo.addons.order_bridge.utils.mobile_auth import messenger_module_ids, resolve_messenger


def _json(payload, status=200):
    return request.make_json_response(
        payload,
        status=status,
        headers=[('Content-Type', 'application/json; charset=utf-8'), *CORS_HEADERS],
    )


class MobileModulesController(http.Controller):
    @http.route(
        '/api/mobile/v1/modules',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    def list_modules(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()
        messenger = resolve_messenger()
        if not messenger:
            return _json({'error': 'unauthorized'}, 401)
        return _json({'modules': messenger_module_ids(messenger)}, 200)
