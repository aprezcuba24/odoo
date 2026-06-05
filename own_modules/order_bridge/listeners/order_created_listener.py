# Part of Odoo. See LICENSE file for full copyright and licensing details.


def order_bridge_order_created(order, old_entity, new_entity):
    if order.order_bridge_origin != 'app':
        return
    print(f'order_bridge: pedido creado desde APK id={order.id} ref={order.order_bridge_ref}')
