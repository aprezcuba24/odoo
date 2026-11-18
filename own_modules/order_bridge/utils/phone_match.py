# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Equivalencia de teléfonos (p. ej. 53024637 == 5353024637) reutilizable en API y filtros."""

from __future__ import annotations

import re

_NON_DIGIT_RE = re.compile(r'\D+')
_EIGHT_DIGITS_RE = re.compile(r'^\d{8}$')
_PLUS_DIGITS_RE = re.compile(r'^\+\d{8,15}$')

DEFAULT_COUNTRY_CALLING_CODE = '53'


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


def canonical_registration_phone(phone_raw) -> str:
    """Return a registration phone in compact E.164, or ``''`` if invalid.

    Accepted inputs:
    - exactly 8 digits (legacy app) → ``+53`` + those digits
    - ``+`` followed by 8–15 digits with no spaces/hyphens; if the number
      starts with ``+53``, the national part must be exactly 8 digits
    """
    if phone_raw is None:
        return ''
    s = str(phone_raw).strip()
    if not s:
        return ''
    if _EIGHT_DIGITS_RE.fullmatch(s):
        return f'+{DEFAULT_COUNTRY_CALLING_CODE}{s}'
    if not _PLUS_DIGITS_RE.fullmatch(s):
        return ''
    if s.startswith(f'+{DEFAULT_COUNTRY_CALLING_CODE}'):
        national = s[len(DEFAULT_COUNTRY_CALLING_CODE) + 1:]
        if len(national) != 8:
            return ''
    return s


def phone_match_domain(phone_raw, *, field='order_bridge_phone_key'):
    """Domain that matches records whose stored phone is equivalent to ``phone_raw``.

    Returns an empty-result domain when ``phone_raw`` has no usable digits.
    """
    key = phone_match_key(phone_raw)
    if not key:
        return [('id', '=', False)]
    return [(field, '=', key)]
