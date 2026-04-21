from odoo import _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero
from own_modules.order_bridge.utils.constant import STATE_DELIVERED


def order_bridge_store_state_changed(order: 'sale.order', old_entity: dict, new_entity: dict):
    """Hook tras persistir un cambio de estado tienda; ampliar en otros módulos (llamar a super)."""
    if order.order_bridge_origin not in ('app', 'admin'):
        return
    if not (new_entity.order_bridge_store_state == STATE_DELIVERED and old_entity["order_bridge_store_state"] != STATE_DELIVERED):
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
