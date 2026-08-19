# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.http import request

_PUBLIC_LANG_PATHS = frozenset({'/web/login', '/web/signup', '/web/reset_password'})


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        if not request:
            return
        path = request.httprequest.path
        if path not in _PUBLIC_LANG_PATHS:
            return
        lang_code = request.env['res.company']._company_onboarding_lang_code()
        if not lang_code:
            return
        request.update_context(lang=lang_code)
        if hasattr(request, 'lang'):
            lang_data = request.env['res.lang']._get_data(code=lang_code)
            if lang_data:
                request.lang = lang_data
