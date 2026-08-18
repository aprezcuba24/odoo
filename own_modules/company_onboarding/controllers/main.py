# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http, tools
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.web.controllers.home import Home, ensure_db

ONBOARDING_COMPANY_PATH = '/web/onboarding/company'


class CompanyOnboardingHome(Home):
    def _login_redirect(self, uid, redirect=None):
        if self._is_onboarding_pending(uid):
            return ONBOARDING_COMPANY_PATH
        return super()._login_redirect(uid, redirect)

    @http.route()
    def web_client(self, s_action=None, **kw):
        ensure_db()
        if request.session.uid and self._is_onboarding_pending(request.session.uid):
            return request.redirect(ONBOARDING_COMPANY_PATH)
        return super().web_client(s_action, **kw)

    @http.route(
        ONBOARDING_COMPANY_PATH,
        type='http',
        auth='user',
        methods=['GET', 'POST'],
        sitemap=False,
    )
    def web_onboarding_company(self, **post):
        user = request.env.user
        if user.has_group('base.group_system') or not user._is_company_onboarding_pending():
            return request.redirect('/odoo')

        values = self._onboarding_company_qcontext(post)
        if request.httprequest.method == 'POST':
            try:
                wiz = request.env['company.onboarding.wizard'].create({
                    'company_name': (post.get('company_name') or '').strip(),
                    'order_bridge_slug': (post.get('order_bridge_slug') or '').strip(),
                    'phone': (post.get('phone') or '').strip() or False,
                    'country_id': self._to_int(post.get('country_id')),
                    'currency_id': self._to_int(post.get('currency_id')),
                })
                wiz.action_create_company()
                return request.redirect('/odoo')
            except (AccessError, UserError, ValidationError) as exc:
                values['error'] = exc.args[0] if exc.args else str(exc)

        response = request.render('company_onboarding.company_form', values)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    def _is_onboarding_pending(self, uid):
        user = request.env['res.users'].sudo().browse(uid)
        return user.exists() and user._is_company_onboarding_pending()

    def _to_int(self, value):
        try:
            return int(value) if value else False
        except (TypeError, ValueError):
            return False

    def _onboarding_company_qcontext(self, post):
        company = request.env.company
        return {
            'disable_database_manager': not tools.config['list_db'],
            'company_name': post.get('company_name', ''),
            'order_bridge_slug': post.get('order_bridge_slug', ''),
            'phone': post.get('phone', ''),
            'country_id': self._to_int(post.get('country_id')) or company.country_id.id,
            'currency_id': self._to_int(post.get('currency_id')) or company.currency_id.id,
            'countries': request.env['res.country'].sudo().search([], order='name'),
            'currencies': request.env['res.currency'].sudo().search(
                [('active', '=', True)],
                order='name',
            ),
        }
