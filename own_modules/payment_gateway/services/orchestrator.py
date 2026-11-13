# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from odoo.tools.float_utils import float_compare, float_round

from odoo.addons.order_bridge.utils.constant import STATE_CANCELED
from odoo.addons.payment_gateway.providers import registry as default_registry
from odoo.addons.payment_gateway.providers.base import PaymentEvent, PaymentProvider
from odoo.addons.payment_gateway.providers.registry import ProviderRegistry


class OrderNotPayable(ValueError):
    """Raised when the order cannot start an online payment."""


class UnknownPaymentAttempt(LookupError):
    """Raised when no payment attempt matches the webhook external id."""


class WebhookAmountMismatch(ValueError):
    """Raised when the webhook amount does not match the stored attempt."""


class PaymentOrchestrator:
    """Resolves providers and starts online charges for sale orders."""

    def __init__(self, env=None, registry: ProviderRegistry | None = None):
        self.env = env
        self._registry = registry if registry is not None else default_registry

    def provider(self, code: str) -> PaymentProvider:
        return self._registry.get(code)

    def start_for_order(self, order, code: str = 'stripe') -> dict:
        """Create or reuse an open PaymentIntent for ``order``.

        Returns a dict suitable for the HTTP response (provider, external_id,
        client_secret, publishable_key, amount, currency).
        """
        if self.env is None:
            raise RuntimeError('PaymentOrchestrator requires an Odoo env')
        order.ensure_one()
        if order.order_bridge_store_state == STATE_CANCELED:
            raise OrderNotPayable('el pedido está cancelado')

        provider = self.provider(code)
        currency_name = order.currency_id.name if order.currency_id else None
        currency_code = provider.charge_currency(currency_name)
        amount_due = self._amount_due(order)
        rounding = order.currency_id.rounding or 0.01
        if float_compare(amount_due, 0.0, precision_rounding=rounding) <= 0:
            raise OrderNotPayable('el saldo del pedido ya está cubierto')

        amount_due = float_round(amount_due, precision_rounding=rounding)

        # Serialize concurrent POSTs for the same order.
        self.env.cr.execute(
            'SELECT id FROM sale_order WHERE id = %s FOR UPDATE',
            (order.id,),
        )

        Attempt = self.env['payment_gateway.payment.attempt'].sudo()
        open_attempt = Attempt.search([
            ('order_id', '=', order.id),
            ('provider_code', '=', code),
            ('state', '=', 'open'),
        ], limit=1, order='id desc')

        if open_attempt:
            if float_compare(
                open_attempt.amount, amount_due, precision_rounding=rounding,
            ) == 0:
                return self._response_payload(open_attempt, provider, code)
            self._cancel_open_attempt(open_attempt, provider)

        start = provider.start_payment(
            amount=amount_due,
            currency=currency_code,
            reference=order.name or str(order.id),
            order_id=order.id,
        )
        client_secret = start.sdk_payload.get('client_secret')
        attempt = Attempt.create({
            'order_id': order.id,
            'provider_code': code,
            'external_id': start.external_id,
            'client_secret': client_secret,
            'state': 'open',
            'amount': amount_due,
            'currency_id': order.currency_id.id,
        })
        if not order.order_bridge_payment_pending:
            order.sudo().write({'order_bridge_payment_pending': True})
        return self._response_payload(attempt, provider, code)

    def status_for_order(self, order, code: str = 'stripe') -> dict:
        """Return paid/due amounts and the latest attempt for ``order``.

        Does not call the provider API. Includes ``client_secret`` and
        publishable config only while the latest attempt is still open
        (``client_config`` may raise ``MissingStripeSecrets`` in that case).
        """
        if self.env is None:
            raise RuntimeError('PaymentOrchestrator requires an Odoo env')
        order.ensure_one()
        Attempt = self.env['payment_gateway.payment.attempt'].sudo()
        attempt = Attempt.search([
            ('order_id', '=', order.id),
            ('provider_code', '=', code),
        ], limit=1, order='id desc')

        currency = (order.currency_id.name or '').strip().lower()
        payload = {
            'provider': code,
            'amount_paid': order.order_bridge_amount_paid,
            'amount_due': order.order_bridge_amount_due,
            'currency': currency,
            'attempt': None,
        }
        if not attempt:
            return payload

        attempt_payload = {
            'state': attempt.state,
            'external_id': attempt.external_id,
            'amount': attempt.amount,
        }
        if attempt.state == 'open':
            provider = self.provider(code)
            attempt_payload['client_secret'] = attempt.sudo().client_secret
            attempt_payload.update(provider.client_config())
        payload['attempt'] = attempt_payload
        return payload

    def apply_webhook_event(self, event: PaymentEvent) -> None:
        """Apply a normalized provider webhook event to the matching attempt."""
        if self.env is None:
            raise RuntimeError('PaymentOrchestrator requires an Odoo env')
        Attempt = self.env['payment_gateway.payment.attempt'].sudo()
        attempt = Attempt.search([
            ('external_id', '=', event.external_id),
        ], limit=1)
        if not attempt:
            raise UnknownPaymentAttempt(
                f'No payment attempt for external_id={event.external_id}'
            )

        self.env.cr.execute(
            'SELECT id FROM payment_gateway_payment_attempt WHERE id = %s FOR UPDATE',
            (attempt.id,),
        )
        attempt.invalidate_recordset()

        if event.status == 'succeeded':
            self._apply_succeeded(attempt, event)
        elif event.status == 'failed':
            self._apply_failed(attempt)
        else:
            raise ValueError(f'Unsupported webhook status: {event.status}')

    def _apply_succeeded(self, attempt, event: PaymentEvent) -> None:
        if attempt.state == 'succeeded':
            return
        if attempt.state == 'canceled':
            return
        rounding = attempt.currency_id.rounding or 0.01
        if float_compare(event.amount, attempt.amount, precision_rounding=rounding) != 0:
            raise WebhookAmountMismatch(
                'el importe del webhook no coincide con el intento'
            )
        method = self.env.ref('payment_gateway.payment_method_stripe').sudo()
        self.env['order_bridge.order.payment'].sudo().create({
            'order_id': attempt.order_id.id,
            'method_id': method.id,
            'amount': attempt.amount,
        })
        attempt.write({'state': 'succeeded'})

    def _apply_failed(self, attempt) -> None:
        if attempt.state == 'open':
            attempt.write({'state': 'failed'})

    def _amount_due(self, order) -> float:
        paid = sum(order.order_bridge_payment_ids.mapped('amount'))
        return order.amount_total - paid

    def _cancel_open_attempt(self, attempt, provider: PaymentProvider) -> None:
        cancel = getattr(provider, 'cancel_payment', None)
        if cancel is not None:
            cancel(external_id=attempt.external_id)
        attempt.write({'state': 'canceled'})

    def _response_payload(self, attempt, provider: PaymentProvider, code: str) -> dict:
        payload = {
            'provider': code,
            'external_id': attempt.external_id,
            'client_secret': attempt.sudo().client_secret,
            'amount': attempt.amount,
            'currency': (
                attempt.currency_id.name or ''
            ).strip().lower(),
        }
        payload.update(provider.client_config())
        return payload
