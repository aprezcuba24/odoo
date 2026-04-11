# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pathlib import Path

from odoo import http
from odoo.http import request

from ..utils.decorators import CORS_HEADERS, api_cors_preflight

_ROOT = Path(__file__).resolve().parent.parent
# Prefer ``static/`` (same URL as ``/order_bridge/static/openapi.json``); fallback ``docs/`` for older trees.
_OPENAPI_FILE = next(
    (p for p in (_ROOT / 'static' / 'openapi.json', _ROOT / 'docs' / 'openapi.json') if p.is_file()),
    _ROOT / 'static' / 'openapi.json',
)


class OpenapiController(http.Controller):
    @http.route(
        '/api/order_bridge/openapi.json',
        type='http',
        auth='public',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    def openapi_json(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return api_cors_preflight()
        if not _OPENAPI_FILE.is_file():
            return request.not_found()
        body = _OPENAPI_FILE.read_bytes()
        return request.make_response(
            body,
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'public, max-age=3600'),
                *CORS_HEADERS,
            ],
        )