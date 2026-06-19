# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.http import request

from ..utils.decorators import get_bearer_device_key


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        if not request.db:
            return
        apk_version = request.httprequest.headers.get('X-App-Version')
        if not apk_version:
            return
        request.env['order_bridge.device'].order_bridge_sync_apk_version(
            get_bearer_device_key(),
            apk_version,
        )
