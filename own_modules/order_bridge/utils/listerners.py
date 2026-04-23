from odoo import _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.addons.order_bridge.utils.constant import STATE_CANCELED, STATE_DELIVERED


def order_bridge_store_state_changed(order, old_entity, new_entity):
    """Hook tras persistir un cambio de estado tienda; ampliar en otros módulos (llamar a super)."""
    if order.order_bridge_origin not in ('app', 'admin'):
        return
    old_ss = old_entity.get('order_bridge_store_state') if old_entity else None
    new_ss = new_entity.order_bridge_store_state
    if old_ss == new_ss:
        return
    _order_bridge_handle_delivered_transition(order, old_ss, new_ss)
    _order_bridge_handle_canceled_transition(order, old_ss, new_ss)


def _order_bridge_handle_delivered_transition(order, old_ss, new_ss):
    if not (new_ss == STATE_DELIVERED and old_ss != STATE_DELIVERED):
        return
    pickings = order.picking_ids.filtered(
        lambda p: p.picking_type_id.code == 'outgoing' and p.state not in ('done', 'cancel')
    ).sorted('id')
    for picking in pickings:
        if picking.state == 'draft':
            picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            rounding = move.product_uom.rounding
            if float_is_zero(move.product_uom_qty, precision_rounding=rounding):
                continue
            if float_is_zero(move.quantity, precision_rounding=rounding):
                move.quantity = move.product_uom_qty
            elif float_compare(move.quantity, move.product_uom_qty, precision_rounding=rounding) < 0:
                move.quantity = move.product_uom_qty
        res = picking.with_context(skip_backorder=True).button_validate()
        if res is not True:
            raise UserError(
                _(
                    'No se pudo validar automáticamente la entrega %(name)s. Revísala en Inventario.',
                    name=picking.display_name,
                )
            )


def _order_bridge_handle_canceled_transition(order, old_ss, new_ss):
    if not (new_ss == STATE_CANCELED and old_ss != STATE_CANCELED):
        return
    if order.state == 'cancel':
        return
    storable_lines = order.order_line.filtered(
        lambda l: not l.display_type
        and not l.is_downpayment
        and l.product_id
        and l.product_id.is_storable
    )
    for line in storable_lines:
        rounding = line.product_uom_id.rounding
        if float_compare(line.qty_delivered, 0.0, precision_rounding=rounding) > 0:
            raise UserError(
                _(
                    'No se puede marcar el pedido como cancelado en tienda mientras quede cantidad '
                    'entregada sin devolver. Registre y complete las devoluciones de inventario '
                    'hasta dejar entregas netas en cero, y luego vuelva a intentarlo.'
                )
            )
    order.action_cancel()
