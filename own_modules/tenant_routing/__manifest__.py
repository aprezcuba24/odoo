# Part of this repository. License: LGPL-3.
{
    'name': 'Tenant Routing & Provision',
    'version': '1.0.0',
    'category': 'Technical',
    'summary': 'Host→DB map (ODOO_TENANT_DOMAIN_MAP) and web UI to provision tenants',
    'description': """
Server-wide multi-tenant helpers (loaded when ODOO_MULTI_TENANT=true):

* Custom domain / Railway default host → database via ODOO_TENANT_DOMAIN_MAP
* Web UI at /tenant/provision (master password + live logs via SSE)
    """,
    'author': 'Local',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
