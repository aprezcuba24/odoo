# Part of Odoo. See LICENSE file for full copyright and licensing details.

from typing import Callable

from odoo import models


class OrderBridgeDispatchMixin(models.AbstractModel):
    _name = 'order_bridge.dispatch.mixin'
    _description = 'Order bridge event dispatch helpers'

    _LISTENERS: list[tuple[Callable, str]] = []

    def on_event(self, name: str, old_entity, new_entity):
        self.ensure_one()
        for listener, listener_name in self._LISTENERS:
            if listener_name == name:
                listener(self, old_entity, new_entity)
