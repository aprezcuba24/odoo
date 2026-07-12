# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    bi_other_cost_id = fields.Many2one(
        'bi.other.cost',
        string='Gasto de consumo',
        readonly=True,
        copy=False,
    )

    def do_scrap(self):
        res = super().do_scrap()
        self._bi_create_other_cost_from_scrap()
        return res

    def _bi_get_scrap_cost_amount(self):
        self.ensure_one()
        move = self.move_ids[:1]
        if move and 'value' in move._fields and move.value:
            return abs(move.value)
        qty_in_product_uom = self.product_uom_id._compute_quantity(
            self.scrap_qty,
            self.product_id.uom_id,
        )
        return qty_in_product_uom * self.product_id.standard_price

    def _bi_create_other_cost_from_scrap(self):
        supply_category = self.env.ref(
            'bi_analytics.cost_category_supply',
            raise_if_not_found=False,
        )
        if not supply_category:
            return

        for scrap in self:
            if (
                scrap.bi_other_cost_id
                or not scrap.product_id
                or scrap.product_id.sale_ok
            ):
                continue

            amount = scrap._bi_get_scrap_cost_amount()
            if amount <= 0:
                continue

            cost = self.env['bi.other.cost'].create({
                'name': f'Consumo {scrap.product_id.display_name}',
                'date': fields.Date.to_date(scrap.date_done or fields.Datetime.now()),
                'amount': amount,
                'category_id': supply_category.id,
                'product_id': scrap.product_id.id,
                'company_id': scrap.company_id.id,
                'currency_id': scrap.company_id.currency_id.id,
                'notes': scrap.name,
                'stock_scrap_id': scrap.id,
            })
            cost.action_confirm()
            scrap.bi_other_cost_id = cost.id
