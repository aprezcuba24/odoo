# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Comercios',
    'version': '19.0.1.5.0',
    'category': 'Ventas/Ventas',
    'summary': 'Venta de productos de comerciantes externos, aislada de Tienda Apk.',
    'description': """
Comercios
=========

Módulo para vender productos de otros comerciantes sin mezclarlos con Tienda Apk
ni con los reportes del negocio. Depende de ``order_bridge`` para reutilizar el
dispositivo (Bearer) y el partner del cliente; la tienda arranca sin él.

En bases con ``company_onboarding``, se activa por compañía en la pestaña
Aplicaciones (apagada por defecto).
    """,
    'depends': ['order_bridge', 'bi_analytics'],
    'data': [
        'security/merchant_store_security.xml',
        'security/ir.model.access.csv',
        'views/merchant_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/merchant_store_menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
