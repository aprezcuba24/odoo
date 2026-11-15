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


def credentials_for_company(env, company) -> StripeCredentials:
    """Return Stripe credentials stored for ``company``.

    Always reads ``payment_gateway.stripe.account``. A missing or incomplete
    row raises ``MissingStripeSecrets`` (same rule for single-tenant and
    multi-company).
    """
    if not company:
        raise MissingStripeSecrets('Stripe credentials require a company')
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
