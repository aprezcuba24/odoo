# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _mcp_api_address_response(self, addr):
        if not addr:
            return False
        return {
            'street': addr.street or '',
            'municipality_id': addr.municipality_id.id if addr.municipality_id else False,
            'municipality_name': addr.municipality_id.name if addr.municipality_id else False,
            'neighborhood_id': addr.neighborhood_id.id if addr.neighborhood_id else False,
            'neighborhood_name': addr.neighborhood_id.name if addr.neighborhood_id else False,
            'state': addr.state or '',
        }

    @api.model
    def _mcp_api_partner_response(self, partner):
        addr = partner.order_bridge_partner_address_ids[:1]
        return {
            'id': partner.id,
            'name': partner.name,
            'phone': partner.phone or False,
            'order_bridge_registered': partner.order_bridge_registered,
            'order_bridge_phone_validated': partner.order_bridge_phone_validated,
            'address': self._mcp_api_address_response(addr),
        }

    @api.model
    def _mcp_api_apk_customer_search_domain(self, query=None):
        """Domain: Tienda Apk customers; optional text match on name, phone or address."""
        domain = [('order_bridge_registered', '=', True)]
        if query is not None and str(query).strip():
            term = str(query).strip()
            domain.extend([
                '|', '|', '|', '|', '|',
                ('name', 'ilike', term),
                ('phone', 'ilike', term),
                ('phone_sanitized', 'ilike', term),
                ('order_bridge_partner_address_ids.street', 'ilike', term),
                ('order_bridge_municipality_id.name', 'ilike', term),
                ('order_bridge_neighborhood_id.name', 'ilike', term),
            ])
        return domain

    @api.model
    def api_search_customers(self, query=None, limit=10):
        """Search Tienda Apk customers by name, phone or delivery address (JSON-2 / MCP).

        Only partners with ``order_bridge_registered`` are returned. When ``query`` is
        omitted or blank, no text filter is applied (list up to ``limit`` APK customers).
        Otherwise ``query`` is matched (ilike) against name, phone, street, municipality
        and neighborhood. Runs as ``self.env.user``; ACL and record rules apply.

        :param str query: Optional free-text search term.
        :param int limit: Max results (capped at 20).
        :returns: list of dicts with id, name, phone, order_bridge flags and address
        """
        limit = min(int(limit or 10), 20)
        partners = self.search(
            self._mcp_api_apk_customer_search_domain(query),
            limit=limit,
            order='name, id',
        )
        return [self._mcp_api_partner_response(partner) for partner in partners]
