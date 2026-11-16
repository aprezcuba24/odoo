# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Resolve Stripe API keys from ``payment_gateway.stripe.account`` rows."""

from __future__ import annotations

from dataclasses import dataclass


class MissingStripeSecrets(RuntimeError):
    """Raised when required Stripe secrets are absent."""


@dataclass(frozen=True)
class StripeCredentials:
    secret_key: str
    publishable_key: str
    webhook_secret: str


def payment_gateway_enabled_for_company(company) -> bool:
    """Return whether Stripe may charge for ``company``.

    Without ``company_onboarding`` (or without the ``payment_gateway`` catalog
    row), charging is allowed whenever credentials exist. With the catalog
    installed, the company must have that optional app enabled.
    """
    if not company:
        return False
    if 'optional_app_ids' not in company._fields:
        return True
    if 'company.optional.app' not in company.env:
        return True
    app = company.env['company.optional.app'].sudo().search(
        [('code', '=', 'payment_gateway')],
        limit=1,
    )
    if not app:
        return True
    return app in company.sudo().optional_app_ids


def credentials_for_company(env, company) -> StripeCredentials:
    """Return Stripe credentials stored for ``company``.

    Always reads ``payment_gateway.stripe.account``. A missing or incomplete
    row raises ``MissingStripeSecrets`` (same rule for single-tenant and
    multi-company). When optional-app gating is active and the company does
    not have Payment Gateway enabled, raises the same error.
    """
    if not company:
        raise MissingStripeSecrets('Stripe credentials require a company')
    if not payment_gateway_enabled_for_company(company):
        raise MissingStripeSecrets(
            'Stripe credentials are not configured for this company'
        )
    Account = env['payment_gateway.stripe.account'].sudo()
    account = Account.search([('company_id', '=', company.id)], limit=1)
    if not account or not account.has_complete_credentials():
        raise MissingStripeSecrets(
            'Stripe credentials are not configured for this company'
        )
    return StripeCredentials(
        secret_key=account.secret_key.strip(),
        publishable_key=account.publishable_key.strip(),
        webhook_secret=account.webhook_secret.strip(),
    )
