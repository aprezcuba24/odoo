# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mobile Order Bridge',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'REST API bridge for Android POS: device key auth and mobile sales orders',
    'description': """
Mobile Order Bridge
===================

Expose JSON REST endpoints for a mobile app: device registration by phone,
admin validation, product catalog, and sale orders (including orders from
non-validated devices, flagged for review).
    """,
    'depends': ['sale', 'product', 'phone_validation', 'point_of_sale'],
    'data': [
        'security/mobile_order_security.xml',
        'security/ir.model.access.csv',
        'data/mobile_order_data.xml',
        'views/mobile_device_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/mobile_menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
