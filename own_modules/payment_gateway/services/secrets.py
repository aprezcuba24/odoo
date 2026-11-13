# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Read Stripe API keys from the process environment."""

from __future__ import annotations

import os


class MissingStripeSecrets(RuntimeError):
    """Raised when required Stripe environment variables are absent."""


def stripe_secret_key() -> str:
    key = (os.environ.get('STRIPE_SECRET_KEY') or '').strip()
    if not key:
        raise MissingStripeSecrets('STRIPE_SECRET_KEY is not configured')
    return key


def stripe_publishable_key() -> str:
    key = (os.environ.get('STRIPE_PUBLISHABLE_KEY') or '').strip()
    if not key:
        raise MissingStripeSecrets('STRIPE_PUBLISHABLE_KEY is not configured')
    return key
