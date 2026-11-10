# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Equivalencia de teléfonos (p. ej. 53024637 == 5353024637) reutilizable en API y filtros."""

from __future__ import annotations

import re

_NON_DIGIT_RE = re.compile(r'\D+')


def phone_digits(phone_raw) -> str:
    """Return only digits; strip a leading international ``00`` prefix."""
    if phone_raw is None:
        return ''
    digits = _NON_DIGIT_RE.sub('', str(phone_raw))
    if digits.startswith('00'):
        digits = digits[2:]
    return digits


def phone_match_key(phone_raw) -> str:
    """Return a stable match key for Cuban-style and other phone numbers.

    ``53`` + 8 national digits (10 digits total) collapses to the 8 national
    digits, so ``53024637``, ``5353024637``, ``+53 5302-4637`` and
    ``005353024637`` share the key ``53024637``. Other numbers use their digits
    as-is (after stripping a leading ``00``).
    """
    digits = phone_digits(phone_raw)
    if not digits:
        return ''
    if len(digits) == 10 and digits.startswith('53'):
        return digits[2:]
    return digits


def phone_match_domain(phone_raw, *, field='order_bridge_phone_key'):
    """Domain that matches records whose stored phone is equivalent to ``phone_raw``.

    Returns an empty-result domain when ``phone_raw`` has no usable digits.
    """
    key = phone_match_key(phone_raw)
    if not key:
        return [('id', '=', False)]
    return [(field, '=', key)]
