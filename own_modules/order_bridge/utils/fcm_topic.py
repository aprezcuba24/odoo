# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Reglas de nombres de topic FCM compartidas entre API (Pydantic) y UI (asistente)."""

from __future__ import annotations

import re

# Nombres de topic FCM: letras, números y -_.~% (sin espacios) — alineado con FCM.
_FCM_TOPIC_RE = re.compile(r'^[a-zA-Z0-9\-_.~%]+$')

#: Mensaje al fallar la validación (mismo criterio que el API JSON).
FCM_TOPIC_INVALID = (
    'Cada topic debe contener solo letras, números y los caracteres -_.~%'
)


def validate_fcm_topic_string(name: str) -> str:
    """Valida y devuelve el topic sin espacios laterales; si no es válido, ``ValueError``."""
    s = (name or '').strip()
    if not s:
        raise ValueError(FCM_TOPIC_INVALID)
    if not _FCM_TOPIC_RE.match(s):
        raise ValueError(FCM_TOPIC_INVALID)
    return s
