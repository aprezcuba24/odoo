# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.order_bridge.utils import order_stock


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _order_bridge_pos_source_location(self):
        self.ensure_one()
        return self.config_id.picking_type_id.default_location_src_id

    def _order_bridge_qty_by_product(self):
        """Positive storable qtys on this order, grouped by product."""
        self.ensure_one()
        qty_by_product = defaultdict(float)
        for line in self.lines:
            if line.qty > 0 and line.product_id:
                qty_by_product[line.product_id.id] += line.qty
        return qty_by_product

    def _order_bridge_assert_pos_stock(self):
        """Raise UserError if positive storable lines exceed free qty on the POS source location."""
        self.ensure_one()
        location = self._order_bridge_pos_source_location()
        if not location:
            return
        qty_by_product = self._order_bridge_qty_by_product()
        if not qty_by_product:
            return
        insufficient = order_stock.check_pos_lines_stock(
            self.env, location, qty_by_product, exclude_order_ids=self.ids,
        )
        if not insufficient:
            return
        lines = []
        for item in insufficient:
            lines.append(_(
                '%(name)s: pide %(requested)s, disponible %(available)s',
                name=item['display_name'],
                requested=item['requested_qty'],
                available=item['available_qty'],
            ))
        raise UserError(_('Stock insuficiente\n%s', '\n'.join(lines)))

    def _process_saved_order(self, draft):
        self.ensure_one()
        if not draft and self.state != 'cancel':
            self._order_bridge_assert_pos_stock()
        return super()._process_saved_order(draft)

    @api.model
    def order_bridge_check_pos_stock(self, config_id, lines):
        """Return whether ``lines`` fit in free stock on the POS source location.

        Uses ``config.picking_type_id.default_location_src_id`` only (no child locations),
        matching standard POS stock deduction.

        ``lines`` is a list of dicts with ``product_id`` and ``qty`` (positive sales only).

        :return: ``{'ok': True}`` or
            ``{'ok': False, 'products': [{'product_id', 'display_name', 'available_qty', 'requested_qty'}, ...]}``
        """
        config = self.env['pos.config'].browse(config_id).exists()
        if not config:
            return {'ok': True}
        location = config.picking_type_id.default_location_src_id
        if not location:
            return {'ok': True}

        qty_by_product = defaultdict(float)
        for line in lines or []:
            product_id = line.get('product_id')
            qty = line.get('qty') or 0.0
            if product_id and qty > 0:
                qty_by_product[int(product_id)] += float(qty)

        insufficient = order_stock.check_pos_lines_stock(
            self.env, location, qty_by_product,
        )
        if insufficient:
            return {'ok': False, 'products': insufficient}
        return {'ok': True}
