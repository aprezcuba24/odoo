# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.payment_gateway.providers.base import (
    PaymentEvent,
    PaymentProvider,
    PaymentStart,
)
from odoo.addons.payment_gateway.providers.registry import (
    DuplicatePaymentProvider,
    InvalidPaymentProvider,
    ProviderRegistry,
    UnknownPaymentProvider,
)
from odoo.addons.payment_gateway.services.orchestrator import PaymentOrchestrator


class FakeProvider(PaymentProvider):
    def start_payment(
        self,
        *,
        amount,
        currency,
        reference,
        order_id=None,
    ):
        return PaymentStart(
            external_id=f'fake_{reference}',
            sdk_payload={'amount': amount, 'currency': currency},
        )

    def parse_webhook(self, *, payload, signature):
        return PaymentEvent(
            external_id='fake_evt',
            status='succeeded',
            amount=1.0,
        )


@tagged('post_install', '-at_install')
class TestGatewayArchitecture(TransactionCase):
    def setUp(self):
        super().setUp()
        self.registry = ProviderRegistry()

    def test_get_registered_provider_returns_instance(self):
        self.registry.register('fake', FakeProvider)
        provider = self.registry.get('fake')
        self.assertIsInstance(provider, FakeProvider)
        start = provider.start_payment(amount=10.0, currency='mxn', reference='SO1')
        self.assertEqual(start.external_id, 'fake_SO1')
        self.assertEqual(start.sdk_payload['amount'], 10.0)

    def test_unknown_code_raises(self):
        with self.assertRaises(UnknownPaymentProvider):
            self.registry.get('missing')

    def test_duplicate_register_raises(self):
        self.registry.register('fake', FakeProvider)
        with self.assertRaises(DuplicatePaymentProvider):
            self.registry.register('fake', FakeProvider)

    def test_invalid_provider_class_raises(self):
        with self.assertRaises(InvalidPaymentProvider):
            self.registry.register('bad', object)

    def test_payment_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            PaymentProvider()

    def test_concrete_subclass_implements_both_methods(self):
        provider = FakeProvider()
        start = provider.start_payment(amount=5.0, currency='usd', reference='R')
        self.assertIsInstance(start, PaymentStart)
        event = provider.parse_webhook(payload=b'{}', signature='sig')
        self.assertIsInstance(event, PaymentEvent)
        self.assertEqual(event.status, 'succeeded')

    def test_orchestrator_resolves_provider(self):
        self.registry.register('fake', FakeProvider)
        orchestrator = PaymentOrchestrator(registry=self.registry)
        provider = orchestrator.provider('fake')
        self.assertIsInstance(provider, FakeProvider)

    def test_orchestrator_propagates_unknown_code(self):
        orchestrator = PaymentOrchestrator(registry=self.registry)
        with self.assertRaises(UnknownPaymentProvider):
            orchestrator.provider('missing')
