# Part of this repository. License: LGPL-3.

{
    'name': 'Tenant Routing',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'summary': 'Map custom hostnames to Odoo databases (multi-tenant).',
    'description': """
Tenant Routing (server-wide)
============================

Loaded as a server-wide module when ``ODOO_MULTI_TENANT=true``.

Extends Odoo ``db_filter`` so that hostnames listed in
``ODOO_TENANT_DOMAIN_MAP`` (JSON object host → database name) resolve to a
single tenant database. Subdomain routing via ``ODOO_DBFILTER`` (e.g. ``^%d$``)
continues to work for hosts not in the map.

Example::

    ODOO_TENANT_DOMAIN_MAP={"tienda.com":"cliente1","app.otro.com":"cliente2"}
    """,
    'depends': ['base'],
    'data': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
