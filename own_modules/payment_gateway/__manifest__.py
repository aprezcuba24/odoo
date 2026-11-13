# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Gateway',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Pasarela de cobros online para Tienda Apk (Stripe como primer proveedor).',
    'description': """
Payment Gateway
===============

Añade la vía de pago Stripe sobre ``order_bridge.payment.method`` para cobros
online de pedidos Tienda Apk. Depende de ``order_bridge``; Tienda Apk arranca
sin este módulo.

Las llamadas a Stripe, secretos, PaymentIntent y webhook llegan en fases
posteriores (ver ``docs/PAGOS_ONLINE.md``).
    """,
    'depends': ['order_bridge'],
    'data': [
        'data/payment_method_data.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
