# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Tienda Apk',
    'version': '19.0.2.0.17',
    'category': 'Ventas/Ventas',
    'summary': 'API REST para aplicaciones externas: catálogo por marca en producto, registro de dispositivo por teléfono y validación en Tienda Apk.',
    'description': """
Tienda Apk
==========

API REST JSON bajo ``/api/order_bridge/`` para apps e integraciones. Los clientes usan una clave de dispositivo (Bearer), no usuarios de Odoo.

**Configuración**

- **Catálogo:** active **Visible en Tienda Apk** en cada plantilla de producto que quieras en la API pública. Solo se listan productos vendibles y activos de la empresa del catálogo (o sin empresa).
- **Dispositivos:** tras ``POST /api/order_bridge/register``, valida los teléfonos en Tienda Apk → Dispositivos cuando confíes en el dispositivo. Los pedidos pueden crearse antes de la validación y quedan marcados para revisión.

**Inventario (cuándo baja el stock)**

Para que un producto gestione existencias y siga el flujo estándar de ventas con inventario, en la **plantilla del producto** debe cumplirse:

- **Tipo de producto:** **Bienes** (no Servicio ni Combo).
- **Rastrear inventario** activado (en inglés *Track Inventory*; campo ``is_storable``). Sin esto el artículo no se trata como almacenable y la API no exige cantidad disponible en almacén.
- **Almacén** configurado para la compañía del catálogo (la creación del pedido por API falla si no hay almacén).

Los pedidos creados por la API se **confirman solos**; Odoo genera las entregas como en una venta normal. La **cantidad a mano** suele **disminuir al validar el albarán de entrega** (transferencia *hecha*), no únicamente al confirmar el pedido (donde puede quedar reservado). Servicios y bienes sin *Rastrear inventario* no descuentan stock físico.

**Depende de:** ventas (sale), ventas e inventario (sale_stock), producto (product), validación de teléfono (phone_validation).
    """,
    'depends': ['sale', 'sale_stock', 'product', 'phone_validation'],
    'external_dependencies': {'python': ['firebase_admin']},
    'data': [
        'security/order_bridge_security.xml',
        'security/ir.model.access.csv',
        'data/order_bridge_data.xml',
        'data/order_bridge_general_settings.xml',
        'views/general_settings_views.xml',
        'views/banner_views.xml',
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
