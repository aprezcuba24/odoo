# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Resolve the Tienda Apk catalog company from request context (slug / host / device)."""

from __future__ import annotations

from odoo.http import request

_RESERVED_SUBDOMAINS = frozenset({
    'www', 'app', 'api', 'admin', 'mail', 'smtp', 'ftp', 'web', 'odoo',
    'static', 'assets', 'health', 'status',
})


def company_slug_from_request(body_slug=None):
    """Return a slug string from body, header, query, or Host subdomain (or None)."""
    if body_slug is not None and str(body_slug).strip():
        return str(body_slug).strip().lower()
    header = request.httprequest.headers.get('X-Company-Slug') or ''
    if header.strip():
        return header.strip().lower()
    query = request.params.get('company_slug') or ''
    if str(query).strip():
        return str(query).strip().lower()
    host = (request.httprequest.host or '').split(':')[0].lower()
    # Skip bare IPs (e.g. 127.0.0.1) — dots look like subdomains.
    if not host or host.replace('.', '').isdigit():
        return None
    parts = host.split('.')
    if len(parts) >= 3:
        sub = parts[0]
        if sub and sub not in _RESERVED_SUBDOMAINS:
            return sub
    return None


def resolve_request_company(body_slug=None, *, required_when_multi=True):
    """Resolve ``res.company`` for public API routes.

    Resolution order: body slug → ``X-Company-Slug`` → query → subdomain →
    single-company DB fallback → ``request.env.company``.

    Returns ``(company, error_payload_or_None, http_status)``.
    ``error_payload`` is a dict suitable for ``SimpleErrorResponse`` when set.
    """
    Company = request.env['res.company'].sudo()
    slug = company_slug_from_request(body_slug)
    if slug:
        company = Company._order_bridge_find_by_slug(slug)
        if not company:
            return Company.browse(), {'error': 'company_not_found'}, 404
        return company, None, 200

    companies = Company.search([])
    if len(companies) == 1:
        return companies, None, 200
    if required_when_multi and len(companies) > 1:
        return Company.browse(), {'error': 'company_slug_required'}, 400
    return request.env.company.sudo(), None, 200
