# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'MCP API (JSON-2)',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Métodos ORM expuestos vía JSON-2 para el servicio MCP (por usuario autenticado).',
    'description': """
MCP API
=======

Expone métodos públicos en modelos estándar (p. ej. ``sale.order``) invocables
desde ``POST /json/2/{model}/{method}`` con Bearer API key de cada ``res.users``.

No sustituye a ``order_bridge`` (app móvil / ``device_key``). Reutiliza utilidades
de ``order_bridge`` cuando hace falta la misma lógica de confirmación y reserva.
    """,
    'depends': ['sale', 'sale_stock', 'order_bridge'],
    'data': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
