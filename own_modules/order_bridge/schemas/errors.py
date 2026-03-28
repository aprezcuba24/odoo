# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pydantic import ValidationError


def pydantic_errors_to_api_body(exc: ValidationError) -> dict:
    """Map Pydantic v2 ValidationError to a stable API error payload."""
    errors = exc.errors()
    if not errors:
        return {
            'error': 'validation',
            'message': 'Validation error',
            'details': [],
        }
    details = [
        {
            'loc': [str(x) for x in e.get('loc', ())],
            'msg': e.get('msg', ''),
            'type': e.get('type', ''),
        }
        for e in errors
    ]
    return {
        'error': 'validation',
        'message': errors[0].get('msg', 'Validation error'),
        'details': details,
    }
