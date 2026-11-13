# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.payment_gateway.providers import registry as default_registry
from odoo.addons.payment_gateway.providers.base import PaymentProvider
from odoo.addons.payment_gateway.providers.registry import ProviderRegistry


class PaymentOrchestrator:
    """Resolves a payment provider by code. Auth, amounts and cobros come later."""

    def __init__(self, registry: ProviderRegistry | None = None):
        self._registry = registry if registry is not None else default_registry

    def provider(self, code: str) -> PaymentProvider:
        return self._registry.get(code)
