# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Company Onboarding',
    'version': '19.0.1.0.0',
    'author': 'Own',
    'category': 'Hidden',
    'summary': 'Self-service signup: cada usuario crea su propia compañía (multi-company en una BD).',
    'description': """
Company Onboarding
==================

Tras el registro público (``auth_signup``), el usuario completa un asistente que:

* Crea una ``res.company`` (nombre, país, moneda, slug Tienda Apk)
* Asigna al usuario solo esa compañía (sin multi-company)
* Concede grupos de operación (ventas, inventario, POS, Tienda Apk) sin derechos de sistema

El proyecto Railway single-tenant de producción no debe instalar este módulo.
    """,
    'depends': [
        'auth_signup',
        'base',
        'web',
        'sales_team',
        'stock',
        'point_of_sale',
        'order_bridge',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/onboarding_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
