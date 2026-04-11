# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Tienda Apk',
    'version': '19.0.2.0.3',
    'category': 'Ventas/Ventas',
    'summary': 'API REST para aplicaciones externas: catálogo por marca en producto, registro de dispositivo por teléfono y validación en Tienda Apk.',
    'description': """
Tienda Apk
==========

API REST JSON bajo ``/api/order_bridge/`` para apps e integraciones. Los clientes usan una clave de dispositivo (Bearer), no usuarios de Odoo.

**Configuración**

- **Catálogo:** active **Visible en Tienda Apk** en cada plantilla de producto que quieras en la API pública. Solo se listan productos vendibles y activos de la empresa del catálogo (o sin empresa).
- **Dispositivos:** tras ``POST /api/order_bridge/register``, valida los teléfonos en Tienda Apk → Dispositivos cuando confíes en el dispositivo. Los pedidos pueden crearse antes de la validación y quedan marcados para revisión.

**Depende de:** ventas (sale), producto (product), validación de teléfono (phone_validation).
    """,
    'depends': ['sale', 'product', 'phone_validation'],
    'data': [
        'security/order_bridge_security.xml',
        'security/ir.model.access.csv',
        'data/order_bridge_data.xml',
        'views/municipality_views.xml',
        'views/device_views.xml',
        'views/res_partner_views.xml',
        'views/res_partner_search_order_bridge.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/order_bridge_menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
