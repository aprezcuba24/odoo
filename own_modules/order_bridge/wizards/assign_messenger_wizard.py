# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.order_bridge.utils.constant import STATE_READY_FOR_DELIVERY


class OrderBridgeAssignMessengerWizard(models.TransientModel):
    _name = 'order_bridge.assign.messenger.wizard'
    _description = 'Asignar mensajero a pedidos seleccionados'

    messenger_id = fields.Many2one(
        'order_bridge.messenger',
        string='Mensajero',
        required=True,
        domain="[('active', '=', True)]",
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        compute='_compute_company_id',
        store=True,
    )
    order_ids = fields.Many2many(
        'sale.order',
        string='Pedidos',
        required=True,
    )
    order_count = fields.Integer(string='Cantidad de pedidos', compute='_compute_order_count')

    @api.depends('order_ids')
    def _compute_company_id(self):
        for wizard in self:
            companies = wizard.order_ids.company_id
            wizard.company_id = companies[:1] if len(companies) == 1 else False

    @api.depends('order_ids')
    def _compute_order_count(self):
        for wizard in self:
            wizard.order_count = len(wizard.order_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'sale.order' and self.env.context.get('active_ids'):
            orders = self.env['sale.order'].browse(self.env.context['active_ids']).exists()
            res['order_ids'] = [(6, 0, orders.ids)]
        return res

    def action_assign(self):
        self.ensure_one()
        orders = self.order_ids
        if not orders:
            raise UserError(_('Seleccione al menos un pedido.'))
        messenger = self.messenger_id
        if not messenger.active:
            raise UserError(_('El mensajero seleccionado no está activo.'))
        for order in orders:
            if order.order_bridge_origin not in ('app', 'admin'):
                raise UserError(
                    _(
                        'El pedido %(name)s no es un pedido de Tienda Apk.',
                        name=order.display_name,
                    )
                )
            if order.order_bridge_store_state != STATE_READY_FOR_DELIVERY:
                raise UserError(
                    _(
                        'El pedido %(name)s debe estar en Listo para entrega '
                        'para asignar un mensajero.',
                        name=order.display_name,
                    )
                )
            if messenger.company_id and order.company_id != messenger.company_id:
                raise UserError(
                    _(
                        'El mensajero %(messenger)s no pertenece a la compañía '
                        'del pedido %(name)s.',
                        messenger=messenger.display_name,
                        name=order.display_name,
                    )
                )
        orders.write({'order_bridge_messenger_id': messenger.id})
        return {
            'type': 'ir.actions.act_window_close',
            'infos': {
                'assigned': True,
                'count': len(orders),
                'messenger_name': messenger.name,
            },
        }
