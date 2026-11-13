# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Gateway',
    'version': '19.0.1.3.0',
    'category': 'Sales/Sales',
    'summary': 'Pasarela de cobros online para Tienda Apk (Stripe como primer proveedor).',
    'description': """
Payment Gateway
===============

Añade la vía de pago Stripe sobre ``order_bridge.payment.method`` para cobros
online de pedidos Tienda Apk. Depende de ``order_bridge``; Tienda Apk arranca
sin este módulo.

PaymentIntent, webhook firmado y estado para la app (puntos 4–6 de
``docs/PAGOS_ONLINE.md``): abre un cobro Stripe, verifica
``payment_intent.succeeded``, escribe una línea ``order_bridge.order.payment``
y expone cobrado / pendiente / intento al dispositivo dueño.
    """,
    'depends': ['order_bridge'],
    'external_dependencies': {'python': ['stripe']},
    'data': [
        'security/ir.model.access.csv',
        'data/payment_method_data.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
