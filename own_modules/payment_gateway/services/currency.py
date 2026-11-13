# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Stripe presentment-currency checks (no HTTP).

Codes from https://docs.stripe.com/currencies (supported presentment currencies).
Account-specific enablement is validated when creating the PaymentIntent (point 4).
"""

# Presentment currencies Stripe documents for card charges (ISO 4217, lowercase).
STRIPE_PRESENTMENT_CURRENCIES = frozenset({
    'aed', 'afn', 'all', 'amd', 'ang', 'aoa', 'ars', 'aud', 'awg', 'azn',
    'bam', 'bbd', 'bdt', 'bif', 'bmd', 'bnd', 'bob', 'brl', 'bsd', 'bwp',
    'byn', 'bzd', 'cad', 'cdf', 'chf', 'clp', 'cny', 'cop', 'crc', 'cve',
    'czk', 'djf', 'dkk', 'dop', 'dzd', 'egp', 'etb', 'eur', 'fjd', 'fkp',
    'gbp', 'gel', 'gip', 'gmd', 'gnf', 'gtq', 'gyd', 'hkd', 'hnl', 'htg',
    'huf', 'idr', 'ils', 'inr', 'isk', 'jmd', 'jpy', 'kes', 'kgs', 'khr',
    'kmf', 'krw', 'kyd', 'kzt', 'lak', 'lbp', 'lkr', 'lrd', 'lsl', 'mad',
    'mdl', 'mga', 'mkd', 'mmk', 'mnt', 'mop', 'mur', 'mvr', 'mwk', 'mxn',
    'myr', 'mzn', 'nad', 'ngn', 'nio', 'nok', 'npr', 'nzd', 'pab', 'pen',
    'pgk', 'php', 'pkr', 'pln', 'pyg', 'qar', 'ron', 'rsd', 'rub', 'rwf',
    'sar', 'sbd', 'scr', 'sek', 'sgd', 'shp', 'sle', 'sos', 'srd', 'std',
    'szl', 'thb', 'tjs', 'top', 'try', 'ttd', 'twd', 'tzs', 'uah', 'ugx',
    'usd', 'uyu', 'uzs', 'vnd', 'vuv', 'wst', 'xaf', 'xcd', 'xcg', 'xof',
    'xpf', 'yer', 'zar', 'zmw',
})


class UnsupportedStripeCurrency(ValueError):
    """Raised when a currency code is empty or not a Stripe presentment currency."""


def normalize_currency_code(code: str | None) -> str:
    """Return a lowercase ISO code, or raise if missing/blank."""
    if code is None:
        raise UnsupportedStripeCurrency('Currency code is required')
    normalized = str(code).strip().lower()
    if not normalized:
        raise UnsupportedStripeCurrency('Currency code is required')
    return normalized


def assert_stripe_currency(code: str | None) -> str:
    """Normalize and assert ``code`` is a Stripe presentment currency.

    Returns the normalized lowercase code for callers that pass it to Stripe.
    """
    normalized = normalize_currency_code(code)
    if normalized not in STRIPE_PRESENTMENT_CURRENCIES:
        raise UnsupportedStripeCurrency(
            f'Currency {normalized!r} is not a Stripe presentment currency'
        )
    return normalized


def order_currency_code(order) -> str:
    """Return the ISO code of ``sale.order.currency_id``, or raise if unset."""
    currency = order.currency_id
    if not currency:
        raise UnsupportedStripeCurrency('Order has no currency')
    return assert_stripe_currency(currency.name)
