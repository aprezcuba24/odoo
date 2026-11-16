# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.payment_gateway.providers.base import PaymentProvider


class UnknownPaymentProvider(KeyError):
    """Raised when no provider is registered for the given code."""


class InvalidPaymentProvider(TypeError):
    """Raised when register receives a class that is not a PaymentProvider."""


class DuplicatePaymentProvider(ValueError):
    """Raised when register is called twice for the same code."""


class ProviderRegistry:
    """Maps provider codes to PaymentProvider subclasses."""

    def __init__(self):
        self._providers: dict[str, type[PaymentProvider]] = {}

    def register(self, code: str, provider_cls: type[PaymentProvider]) -> None:
        if not isinstance(provider_cls, type) or not issubclass(provider_cls, PaymentProvider):
            raise InvalidPaymentProvider(
                f'{provider_cls!r} must be a subclass of PaymentProvider'
            )
        if code in self._providers:
            raise DuplicatePaymentProvider(
                f'Payment provider already registered for code {code!r}'
            )
        self._providers[code] = provider_cls

    def get_class(self, code: str) -> type[PaymentProvider]:
        try:
            return self._providers[code]
        except KeyError as err:
            raise UnknownPaymentProvider(
                f'No payment provider registered for code {code!r}'
            ) from err

    def get(self, code: str, credentials=None) -> PaymentProvider:
        provider_cls = self.get_class(code)
        try:
            return provider_cls(credentials=credentials)
        except TypeError:
            return provider_cls()


_REGISTRY = ProviderRegistry()


def register(code: str, provider_cls: type[PaymentProvider]) -> None:
    _REGISTRY.register(code, provider_cls)


def get_class(code: str) -> type[PaymentProvider]:
    return _REGISTRY.get_class(code)


def get(code: str, credentials=None) -> PaymentProvider:
    return _REGISTRY.get(code, credentials=credentials)
