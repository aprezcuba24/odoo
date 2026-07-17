# Part of this repository. License: LGPL-3.
"""Monkey-patch odoo.http.db_filter for custom domain → database mapping."""

from __future__ import annotations

import json
import logging
import os

from odoo import http
from odoo.tools import config

_logger = logging.getLogger(__name__)

_db_filter_org = http.db_filter


def _normalize_host(host: str) -> str:
    host = (host or '').partition(':')[0].lower()
    if host.startswith('www.'):
        host = host[4:]
    return host


def _load_domain_map() -> dict[str, str]:
    raw = os.environ.get('ODOO_TENANT_DOMAIN_MAP', '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        _logger.error('ODOO_TENANT_DOMAIN_MAP is not valid JSON; ignoring.')
        return {}
    if not isinstance(data, dict):
        _logger.error('ODOO_TENANT_DOMAIN_MAP must be a JSON object; ignoring.')
        return {}
    return {_normalize_host(str(k)): str(v) for k, v in data.items() if k and v}


def db_filter(dbs, host=None):
    """Prefer ODOO_TENANT_DOMAIN_MAP; otherwise use standard dbfilter (%d / %h)."""
    if host is None and http.request:
        host = http.request.httprequest.environ.get('HTTP_HOST', '')
    normalized = _normalize_host(host or '')
    domain_map = _load_domain_map()
    if normalized and normalized in domain_map:
        target = domain_map[normalized]
        return [db for db in dbs if db == target]
    return _db_filter_org(dbs, host)


# Always patch when this server-wide module is loaded (multi-tenant WSGI loads it).
_logger.info('tenant_routing: patching http.db_filter (custom domain map)')
http.db_filter = db_filter

# Ensure proxy_mode is on when a domain map is present (Railway TLS termination).
if _load_domain_map() and not config.get('proxy_mode'):
    _logger.warning(
        'ODOO_TENANT_DOMAIN_MAP is set but proxy_mode is False; '
        'set ODOO_PROXY_MODE=true so Host / X-Forwarded-Host are trusted.'
    )
