# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Company Onboarding',
    'version': '19.0.1.3.0',
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
* Aísla el catálogo por compañía (productos, tarifas, categorías nuevas) sin compartir ``company_id`` vacío

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
        'security/company_onboarding_security.xml',
        'data/ir_config_parameter.xml',
        'data/default_lang.xml',
        'views/onboarding_templates.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
