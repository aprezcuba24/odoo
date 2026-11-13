# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from odoo.tools.float_utils import float_compare, float_round

from odoo.addons.order_bridge.utils.constant import STATE_CANCELED
from odoo.addons.payment_gateway.providers import registry as default_registry
from odoo.addons.payment_gateway.providers.base import PaymentProvider
from odoo.addons.payment_gateway.providers.registry import ProviderRegistry


class OrderNotPayable(ValueError):
    """Raised when the order cannot start an online payment."""


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
