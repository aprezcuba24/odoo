# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Shared helpers for payment_gateway tests."""

from odoo import Command


def enable_payment_gateway_app(env, *companies):
    """Enable optional Payment Gateway on ``companies`` when the catalog exists.

    No-op on single-tenant DBs without ``company_onboarding``.
    """
    if 'company.optional.app' not in env:
        return
    app = env.ref(
        'company_onboarding.optional_app_payment_gateway',
        raise_if_not_found=False,
    )
    if not app:
        app = env['company.optional.app'].sudo().search(
            [('code', '=', 'payment_gateway')],
            limit=1,
        )
    if not app:
        return
    for company in companies:
        if company and app not in company.optional_app_ids:
            company.sudo().write({'optional_app_ids': [Command.link(app.id)]})
