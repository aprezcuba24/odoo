# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Stripe adapter: PaymentIntent create/cancel and signed webhook parsing."""

from __future__ import annotations

import logging

from odoo.addons.payment_gateway.providers.base import PaymentEvent, PaymentProvider, PaymentStart
from odoo.addons.payment_gateway.providers.registry import register
from odoo.addons.payment_gateway.services.currency import (
    assert_stripe_currency,
    from_stripe_minor_units,
    to_stripe_minor_units,
)
from odoo.addons.payment_gateway.services.secrets import (
    MissingStripeSecrets,
    StripeCredentials,
)

_logger = logging.getLogger(__name__)


class StripeProviderError(RuntimeError):
    """Raised when the Stripe API call fails."""


class StripeWebhookSignatureError(ValueError):
    """Raised when the webhook signature or payload cannot be verified."""


class StripeWebhookIgnoredEvent(ValueError):
    """Raised when the webhook event type is not handled."""


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


def _event_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class StripeProvider(PaymentProvider):
    """Adapter for Stripe PaymentIntents."""

    def __init__(self, client=None, webhook_construct=None, credentials=None):
        self._client = client
        self._webhook_construct = webhook_construct
        self._credentials = credentials

    def _creds(self) -> StripeCredentials:
        if self._credentials is None:
            raise MissingStripeSecrets('Stripe credentials were not provided')
        return self._credentials

    def charge_currency(self, code: str | None) -> str:
        return assert_stripe_currency(code)

    def client_config(self) -> dict:
        return {'publishable_key': self._creds().publishable_key}

    def _payment_intents(self):
        if self._client is not None:
            return self._client.PaymentIntent
        return _import_stripe().PaymentIntent

    def _construct_event(self, payload: bytes, signature: str, secret: str):
        if self._webhook_construct is not None:
            return self._webhook_construct(payload, signature, secret)
        stripe = _import_stripe()
        return stripe.Webhook.construct_event(payload, signature, secret)

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
        idempotency_key = f'pgw2-{key_ref}-{minor}-{currency}'
        metadata = {'reference': reference}
        if order_id is not None:
            metadata['order_id'] = str(order_id)
        create_kwargs = {
            'amount': minor,
            'currency': currency,
            'allowed_payment_method_types': ['card'],
            'metadata': metadata,
            'api_key': self._creds().secret_key,
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
        if not signature:
            raise StripeWebhookSignatureError('Missing Stripe-Signature header')
        try:
            secret = self._creds().webhook_secret
        except MissingStripeSecrets:
            raise
        try:
            event = self._construct_event(payload, signature, secret)
        except StripeWebhookSignatureError:
            raise
        except Exception as err:
            # Stripe raises SignatureVerificationError / ValueError on bad payload.
            _logger.warning('Stripe webhook verification failed: %s', err)
            raise StripeWebhookSignatureError('Invalid Stripe webhook signature') from err

        event_type = _event_get(event, 'type')
        data = _event_get(event, 'data') or {}
        intent = _event_get(data, 'object') or {}
        external_id = _event_get(intent, 'id')
        if not external_id:
            raise StripeWebhookSignatureError('Webhook event missing PaymentIntent id')

        currency = assert_stripe_currency(_event_get(intent, 'currency'))
        amount_minor = _event_get(intent, 'amount')
        if amount_minor is None:
            amount_minor = _event_get(intent, 'amount_received', 0)
        amount = from_stripe_minor_units(int(amount_minor), currency)

        if event_type == 'payment_intent.succeeded':
            return PaymentEvent(
                external_id=str(external_id),
                status='succeeded',
                amount=amount,
            )
        if event_type == 'payment_intent.payment_failed':
            return PaymentEvent(
                external_id=str(external_id),
                status='failed',
                amount=amount,
            )
        raise StripeWebhookIgnoredEvent(f'Unhandled Stripe event type: {event_type}')

    def cancel_payment(self, *, external_id: str) -> None:
        try:
            self._payment_intents().cancel(
                external_id,
                api_key=self._creds().secret_key,
            )
        except Exception as err:
            if not _is_stripe_error(err):
                raise
            _logger.exception('Stripe PaymentIntent.cancel failed for %s', external_id)
            raise StripeProviderError('Stripe payment could not be canceled') from err


register('stripe', StripeProvider)
