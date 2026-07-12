# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Inteligencia de Negocio',
    'version': '19.0.1.0.0',
    'category': 'Ventas/Informes',
    'summary': 'Reportes de inteligencia de negocio.',
    'description': """
Inteligencia de Negocio
=======================

Reportes analíticos sobre ventas confirmadas.
    """,
    'depends': ['sale', 'sale_margin'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_sale_report_views.xml',
        'views/bi_analytics_menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
