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
    order_ref = fields.Char(string='Referencia del pedido', readonly=True)
    sale_origin = fields.Selection(
        selection=[
            ('apk', 'Apk'),
            ('pos', 'POS'),
            ('sale', 'Venta'),
        ],
        string='Origen de venta',
        readonly=True,
    )
    qty_sold = fields.Float(string='Ventas', readonly=True)
    sale_amount = fields.Monetary(string='Importe de venta', readonly=True)
    cost_amount = fields.Monetary(string='Costo de venta', readonly=True)
    profit_amount = fields.Monetary(string='Ganancia', readonly=True)

    _depends = {
        'sale.order': ['state', 'company_id', 'date_order', 'name'],
        'sale.order.line': [
            'product_id',
            'product_uom_qty',
            'qty_delivered',
            'price_unit',
            'purchase_price',
            'display_type',
        ],
        'stock.move': ['sale_line_id', 'state', 'origin_returned_move_id'],
        'pos.order': ['state', 'company_id', 'date_order', 'name'],
        'pos.order.line': [
            'product_id',
            'qty',
            'price_unit',
            'price_subtotal',
            'total_cost',
        ],
        'product.product': ['product_tmpl_id'],
        'product.template': ['categ_id'],
    }

    @property
    def _table_query(self) -> SQL:
        return SQL(
            '%s UNION ALL %s',
            self._sale_order_query(),
            self._pos_order_query(),
        )

    def _sale_origin_sql(self) -> SQL:
        if 'order_bridge_origin' in self.env['sale.order']._fields:
            return SQL(
                "CASE WHEN s.order_bridge_origin IS NOT NULL THEN 'apk' ELSE 'sale' END",
            )
        return SQL("'sale'")

    def _sale_order_query(self) -> SQL:
        # Use net delivered qty when stock moves exist; keep ordered qty for
        # confirmed lines not yet delivered. Exclude fully returned lines
        # (qty_delivered = 0 after a done outgoing move).
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
                    s.name AS order_ref,
                    %s AS sale_origin,
                    CASE
                        WHEN l.qty_delivered > 0 THEN l.qty_delivered
                        ELSE l.product_uom_qty
                    END AS qty_sold,
                    l.price_unit * (
                        CASE
                            WHEN l.qty_delivered > 0 THEN l.qty_delivered
                            ELSE l.product_uom_qty
                        END
                    ) AS sale_amount,
                    l.purchase_price * (
                        CASE
                            WHEN l.qty_delivered > 0 THEN l.qty_delivered
                            ELSE l.product_uom_qty
                        END
                    ) AS cost_amount,
                    (l.price_unit - l.purchase_price) * (
                        CASE
                            WHEN l.qty_delivered > 0 THEN l.qty_delivered
                            ELSE l.product_uom_qty
                        END
                    ) AS profit_amount
                FROM sale_order_line l
                JOIN sale_order s ON s.id = l.order_id
                JOIN res_company c ON c.id = s.company_id
                LEFT JOIN product_product p ON p.id = l.product_id
                LEFT JOIN product_template t ON t.id = p.product_tmpl_id
                WHERE s.state = 'sale'
                  AND l.display_type IS NULL
                  AND l.product_id IS NOT NULL
                  AND NOT (
                      l.qty_delivered = 0
                      AND EXISTS (
                          SELECT 1
                          FROM stock_move sm
                          WHERE sm.sale_line_id = l.id
                            AND sm.state = 'done'
                            AND sm.origin_returned_move_id IS NULL
                      )
                  )
            """,
            self._sale_origin_sql(),
        )

    def _pos_order_query(self) -> SQL:
        exclude_linked = SQL('')
        if 'sale_order_line_id' in self.env['pos.order.line']._fields:
            exclude_linked = SQL('AND l.sale_order_line_id IS NULL')
        return SQL(
            """
                SELECT
                    l.id + 1000000000 AS id,
                    l.product_id AS product_id,
                    p.product_tmpl_id AS product_tmpl_id,
                    t.categ_id AS categ_id,
                    o.company_id AS company_id,
                    c.currency_id AS currency_id,
                    o.date_order AS date_order,
                    o.name AS order_ref,
                    'pos' AS sale_origin,
                    l.qty AS qty_sold,
                    (SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal)) AS sale_amount,
                    COALESCE(l.total_cost, 0) AS cost_amount,
                    (SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal)) - COALESCE(l.total_cost, 0) AS profit_amount
                FROM pos_order_line l
                JOIN pos_order o ON o.id = l.order_id
                JOIN res_company c ON c.id = o.company_id
                LEFT JOIN product_product p ON p.id = l.product_id
                LEFT JOIN product_template t ON t.id = p.product_tmpl_id
                WHERE o.state IN ('paid', 'done')
                  AND l.product_id IS NOT NULL
                  %s
            """,
            exclude_linked,
        )

