# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Company Onboarding',
    'version': '19.0.1.2.0',
    'author': 'Own',
    'category': 'Hidden',
    'summary': 'Self-service signup: cada usuario crea su propia compañía (multi-company en una BD).',
    'description': """
Company Onboarding
==================

Tras el registro público (``auth_signup``), el usuario completa un asistente
en dos pasos (cuenta + compañía) con el estilo de login:

* Crea una ``res.company`` (nombre, país, moneda, slug Tienda Apk)
* Asigna al usuario solo esa compañía (sin multi-company)
* Concede grupos de operación (ventas, inventario admin, POS admin, productos, facturación, Tienda Apk) sin derechos de sistema
* Carga un plan de cuentas y un punto de venta inicial en la nueva compañía

El usuario no entra a la aplicación hasta terminar el asistente.
El proyecto Railway single-tenant de producción no debe instalar este módulo.
    """,
    'depends': [
        'auth_signup',
        'base',
        'web',
        'sales_team',
        'stock',
        'product',
        'account',
        'point_of_sale',
        'order_bridge',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/onboarding_templates.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
