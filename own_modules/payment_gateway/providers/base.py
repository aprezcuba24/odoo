# Part of Odoo. See LICENSE file for full copyright and licensing details.

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentStart:
    """Result of opening a remote charge (e.g. PaymentIntent)."""

    external_id: str
    sdk_payload: dict


@dataclass(frozen=True)
class PaymentEvent:
    """Normalized webhook event after signature verification."""

    external_id: str
    status: str  # 'succeeded' | 'failed'
    amount: float


class PaymentProvider(ABC):
    """Strategy interface for an online payment provider."""

    @abstractmethod
    def start_payment(
        self,
        *,
        amount: float,
        currency: str,
        reference: str,
    ) -> PaymentStart:
        """Open a remote charge and return ids plus SDK payload."""

    @abstractmethod
    def parse_webhook(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> PaymentEvent:
        """Verify the raw body signature and return a normalized event."""
