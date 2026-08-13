# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.http import request


class CompanyOnboardingHome(Home):
    def _login_redirect(self, uid, redirect=None):
        user = request.env['res.users'].sudo().browse(uid)
        if user.exists() and user._is_company_onboarding_pending():
            return '/odoo/action-company_onboarding.action_company_onboarding_wizard'
        return super()._login_redirect(uid, redirect)
