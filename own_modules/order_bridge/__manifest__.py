# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Order Bridge',
    'version': '19.0.2.0.1',
    'category': 'Sales/Sales',
    'summary': 'REST API for external apps: link a POS per company, register devices by phone, validate in Order Bridge.',
    'description': """
Order Bridge
============

JSON REST API under ``/api/order_bridge/`` for apps and integrations. Clients use a device key (Bearer), not Odoo logins.

**Setup**

- **Point of Sale → Order bridge:** choose the POS whose products and category rules define the public catalog (or set the same on the company). Required; otherwise catalog and orders return HTTP 503.
- **Devices:** after ``POST /api/order_bridge/register``, validate phones in Order Bridge → Devices when you trust the device. Orders can be created before validation and are marked for review.

**Depends on:** sale, point_of_sale, product, phone_validation.
    """,
    'depends': ['sale', 'product', 'phone_validation', 'point_of_sale', 'pos_sale'],
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
