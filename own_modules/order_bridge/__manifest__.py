# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Order Bridge',
    'version': '19.0.2.0.2',
    'category': 'Sales/Sales',
    'summary': 'REST API for external apps: catalog by product flag, device registration by phone, validate in Order Bridge.',
    'description': """
Order Bridge
============

JSON REST API under ``/api/order_bridge/`` for apps and integrations. Clients use a device key (Bearer), not Odoo logins.

**Setup**

- **Catalog:** enable **Visible in Order bridge** on each product template you want in the public API. Only saleable, active products for the catalog company (or without company) are listed.
- **Devices:** after ``POST /api/order_bridge/register``, validate phones in Order Bridge → Devices when you trust the device. Orders can be created before validation and are marked for review.

**Depends on:** sale, product, phone_validation.
    """,
    'depends': ['sale', 'product', 'phone_validation'],
    'data': [
        'security/order_bridge_security.xml',
        'security/ir.model.access.csv',
        'data/order_bridge_data.xml',
        'views/device_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/order_bridge_menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
