# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools.sql import SQL


class BiProductSaleReport(models.Model):
    _name = 'bi.product.sale.report'
    _description = 'Reporte de ventas por producto'
    _auto = False
    _rec_name = 'product_id'
    _order = 'sale_amount desc'

    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Plantilla de producto', readonly=True)
    categ_id = fields.Many2one('product.category', string='Categoría de producto', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    date_order = fields.Datetime(string='Fecha del pedido', readonly=True)
    qty_sold = fields.Float(string='Cantidad', readonly=True)
    sale_amount = fields.Monetary(string='Venta', readonly=True)
    cost_amount = fields.Monetary(string='Costo', readonly=True)
    profit_amount = fields.Monetary(string='Ganancia', readonly=True)

    _depends = {
        'sale.order': ['state', 'company_id', 'date_order'],
        'sale.order.line': [
            'product_id',
            'product_uom_qty',
            'price_unit',
            'purchase_price',
            'display_type',
        ],
        'product.product': ['product_tmpl_id'],
        'product.template': ['categ_id'],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL('%s %s %s', self._select(), self._from(), self._where())

    def _select(self) -> SQL:
        return SQL(
            """
                SELECT
                    l.id AS id,
                    l.product_id AS product_id,
                    p.product_tmpl_id AS product_tmpl_id,
                    t.categ_id AS categ_id,
                    s.company_id AS company_id,
                    c.currency_id AS currency_id,
                    s.date_order AS date_order,
                    l.product_uom_qty AS qty_sold,
                    l.price_unit * l.product_uom_qty AS sale_amount,
                    l.purchase_price * l.product_uom_qty AS cost_amount,
                    (l.price_unit - l.purchase_price) * l.product_uom_qty AS profit_amount
            """,
        )

    def _from(self) -> SQL:
        return SQL(
            """
                FROM sale_order_line l
                JOIN sale_order s ON s.id = l.order_id
                JOIN res_company c ON c.id = s.company_id
                LEFT JOIN product_product p ON p.id = l.product_id
                LEFT JOIN product_template t ON t.id = p.product_tmpl_id
            """,
        )

    def _where(self) -> SQL:
        return SQL(
            """
                WHERE s.state = 'sale'
                  AND l.display_type IS NULL
                  AND l.product_id IS NOT NULL
            """,
        )
