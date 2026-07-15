# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Inteligencia de Negocio',
    'version': '19.0.1.5.0',
    'category': 'Ventas/Informes',
    'summary': 'Reportes de inteligencia de negocio.',
    'description': """
Inteligencia de Negocio
=======================

Reportes analíticos sobre ventas confirmadas (incl. TPV), gastos y rentabilidad.
Incluye catálogo de insumos y registro de consumos.
    """,
    'depends': ['sale', 'sale_margin', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/cost_category_data.xml',
        'views/cost_category_views.xml',
        'views/supply_views.xml',
        'views/supply_entry_views.xml',
        'views/other_cost_views.xml',
        'views/profitability_report_views.xml',
        'views/product_sale_report_views.xml',
        'views/other_cost_report_views.xml',
        'views/bi_analytics_menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
