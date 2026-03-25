# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Order Bridge',
    'version': '19.0.2.0.0',
    'category': 'Sales/Sales',
    'summary': 'REST API bridge: device key auth, catalog, and external client sales orders',
    'description': """
Order Bridge
============

Expose JSON REST endpoints for external clients (apps, kiosks, integrations):
device registration by phone, admin validation, product catalog aligned to a
POS config, and sale orders (including orders from non-validated devices,
flagged for review).
    """,
    'depends': ['sale', 'product', 'phone_validation', 'point_of_sale'],
    'data': [
        'security/order_bridge_security.xml',
        'security/ir.model.access.csv',
        'data/order_bridge_data.xml',
        'views/device_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/order_bridge_menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
