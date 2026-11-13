# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Stripe adapter: PaymentIntent create/cancel. Webhook parsing is point 5."""

from __future__ import annotations

import logging

from odoo.addons.payment_gateway.providers.base import PaymentEvent, PaymentProvider, PaymentStart
from odoo.addons.payment_gateway.providers.registry import register
from odoo.addons.payment_gateway.services.currency import (
    assert_stripe_currency,
    to_stripe_minor_units,
)
from odoo.addons.payment_gateway.services.secrets import (
    stripe_publishable_key,
    stripe_secret_key,
)

_logger = logging.getLogger(__name__)


class StripeProviderError(RuntimeError):
    """Raised when the Stripe API call fails."""


class StripeWebhookNotImplemented(NotImplementedError):
    """parse_webhook is implemented in point 5."""


def _import_stripe():
    try:
        import stripe
    except ImportError as err:
        raise StripeProviderError(
            'The stripe Python package is not installed'
        ) from err
    return stripe


def _is_stripe_error(exc: BaseException) -> bool:
    return exc.__class__.__module__.startswith('stripe')


class StripeProvider(PaymentProvider):
    """Adapter for Stripe PaymentIntents."""

    def __init__(self, client=None):
        self._client = client

    def charge_currency(self, code: str | None) -> str:
        return assert_stripe_currency(code)

    def client_config(self) -> dict:
        return {'publishable_key': stripe_publishable_key()}

    def _payment_intents(self):
        if self._client is not None:
            return self._client.PaymentIntent
        return _import_stripe().PaymentIntent

    def start_payment(
        self,
        *,
        amount: float,
        currency: str,
        reference: str,
        order_id: int | None = None,
    ) -> PaymentStart:
        currency = self.charge_currency(currency)
        minor = to_stripe_minor_units(amount, currency)
        key_ref = order_id if order_id is not None else reference
        idempotency_key = f'pgw-{key_ref}-{minor}-{currency}'
        metadata = {'reference': reference}
        if order_id is not None:
            metadata['order_id'] = str(order_id)
        create_kwargs = {
            'amount': minor,
            'currency': currency,
            'payment_method_types': ['card'],
            'metadata': metadata,
            'api_key': stripe_secret_key(),
            'idempotency_key': idempotency_key,
        }
        try:
            intent = self._payment_intents().create(**create_kwargs)
        except Exception as err:
            if not _is_stripe_error(err):
                raise
            _logger.exception('Stripe PaymentIntent.create failed for %s', reference)
            raise StripeProviderError('Stripe payment could not be started') from err
        external_id = intent['id'] if isinstance(intent, dict) else intent.id
        client_secret = (
            intent['client_secret'] if isinstance(intent, dict) else intent.client_secret
        )
        return PaymentStart(
            external_id=external_id,
            sdk_payload={'client_secret': client_secret},
        )

    def parse_webhook(self, *, payload: bytes, signature: str) -> PaymentEvent:
        raise StripeWebhookNotImplemented(
            'Stripe webhook parsing is implemented in point 5'
        )

    def cancel_payment(self, *, external_id: str) -> None:
        try:
            self._payment_intents().cancel(
                external_id,
                api_key=stripe_secret_key(),
            )
        except Exception as err:
            if not _is_stripe_error(err):
                raise
            _logger.exception('Stripe PaymentIntent.cancel failed for %s', external_id)
            raise StripeProviderError('Stripe payment could not be canceled') from err


register('stripe', StripeProvider)
