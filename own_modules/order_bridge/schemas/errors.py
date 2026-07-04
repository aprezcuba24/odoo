# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any

from pydantic import ValidationError


def _spanish_pydantic_msg(error: dict[str, Any]) -> str:
    """Translate built-in Pydantic v2 messages to Spanish for API clients."""
    err_type = error.get('type', '')
    ctx = error.get('ctx') or {}
    loc = error.get('loc', ())

    if err_type == 'missing':
        return 'Campo obligatorio'
    if err_type == 'greater_than':
        limit = ctx.get('gt')
        if limit is not None:
            return f'Debe ser mayor que {limit}'
        return 'Debe ser mayor que el valor mínimo'
    if err_type == 'greater_than_equal':
        limit = ctx.get('ge')
        if limit is not None:
            return f'Debe ser mayor o igual que {limit}'
        return 'Debe ser mayor o igual que el valor mínimo'
    if err_type == 'int_parsing':
        return 'Debe ser un número entero'
    if err_type == 'float_parsing':
        return 'Debe ser un número'
    if err_type == 'string_too_short':
        return 'No puede estar vacío'
    if err_type == 'list_min_length':
        return 'Debe incluir al menos un elemento'
    if err_type == 'literal_error':
        if loc and loc[-1] == 'platform':
            return 'La plataforma debe ser android o ios'
        return 'Valor no permitido'
    return error.get('msg', 'Error de validación')


def pydantic_errors_to_api_body(exc: ValidationError) -> dict:
    """Map Pydantic v2 ValidationError to a stable API error payload."""
    errors = exc.errors()
    if not errors:
        return {
            'error': 'validation',
            'message': 'Error de validación',
            'details': [],
        }
    details = [
        {
            'loc': [str(x) for x in e.get('loc', ())],
            'msg': _spanish_pydantic_msg(e),
            'type': e.get('type', ''),
        }
        for e in errors
    ]
    return {
        'error': 'validation',
        'message': details[0]['msg'],
        'details': details,
    }
