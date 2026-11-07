# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Inteligencia de Negocio',
    'version': '19.0.1.0.0',
    'category': 'Ventas/Informes',
    'summary': 'Reportes de inteligencia de negocio.',
    'description': """
Inteligencia de Negocio
=======================

Reportes analíticos sobre ventas confirmadas (incl. TPV), gastos y rentabilidad.
Incluye catálogo de insumos, registro de consumos y salud del negocio
(valor de inventario y crecimiento por cuartiles).
    """,
    'depends': ['sale', 'sale_margin', 'sale_stock', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'security/bi_analytics_security.xml',
        'data/cost_category_data.xml',
        'views/cost_category_views.xml',
        'views/supply_views.xml',
        'views/supply_entry_views.xml',
        'views/other_cost_views.xml',
        'views/profitability_report_views.xml',
        'views/product_sale_report_views.xml',
        'views/other_cost_report_views.xml',
        'views/business_health_views.xml',
        'views/bi_analytics_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bi_analytics/static/src/scss/profitability_summary.scss',
            'bi_analytics/static/src/scss/business_health.scss',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
