# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
import statistics
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.fields import Command
from odoo.tools.float_utils import float_is_zero


class BiBusinessHealth(models.TransientModel):
    _name = 'bi.business.health'
    _description = 'Salud del negocio'

    date_from = fields.Date(string='Periodo', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    previous_date_from = fields.Date(string='Periodo anterior desde', readonly=True)
    previous_date_to = fields.Date(string='Periodo anterior hasta', readonly=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
    )
    display_name = fields.Char(compute='_compute_display_name', store=False)

    # Global growth
    sale_amount = fields.Monetary(string='Importe de venta', readonly=True)
    sale_amount_prev = fields.Monetary(string='Venta periodo anterior', readonly=True)
    sale_growth_pct = fields.Float(string='Crecimiento de venta (%)', readonly=True, digits=(16, 2))
    qty_sold = fields.Float(string='Unidades vendidas', readonly=True, digits='Product Unit')
    qty_sold_prev = fields.Float(string='Unidades periodo anterior', readonly=True, digits='Product Unit')
    qty_growth_pct = fields.Float(string='Crecimiento de unidades (%)', readonly=True, digits=(16, 2))
    order_count = fields.Integer(string='Pedidos', readonly=True)
    order_count_prev = fields.Integer(string='Pedidos periodo anterior', readonly=True)
    order_growth_pct = fields.Float(string='Crecimiento de pedidos (%)', readonly=True, digits=(16, 2))
    avg_ticket = fields.Monetary(string='Ticket promedio', readonly=True)
    avg_ticket_prev = fields.Monetary(string='Ticket promedio anterior', readonly=True)
    avg_ticket_growth_pct = fields.Float(
        string='Crecimiento de ticket (%)',
        readonly=True,
        digits=(16, 2),
    )
    cost_amount = fields.Monetary(string='Costo de venta', readonly=True)
    cost_amount_prev = fields.Monetary(string='Costo periodo anterior', readonly=True)
    profit_amount = fields.Monetary(string='Ganancia bruta', readonly=True)
    profit_amount_prev = fields.Monetary(string='Ganancia bruta anterior', readonly=True)
    profit_growth_pct = fields.Float(string='Crecimiento de ganancia (%)', readonly=True, digits=(16, 2))
    margin_pct = fields.Float(string='Margen bruto (%)', readonly=True, digits=(16, 2))
    margin_pct_prev = fields.Float(string='Margen bruto anterior (%)', readonly=True, digits=(16, 2))

    # Inventory snapshot
    product_inventory_value = fields.Monetary(string='Valor inventario productos', readonly=True)
    supply_inventory_value = fields.Monetary(string='Valor inventario insumos', readonly=True)
    net_inventory_value = fields.Monetary(string='Valor neto del inventario', readonly=True)
    zero_cost_product_count = fields.Integer(string='Productos con stock y costo cero', readonly=True)
    zero_cost_supply_count = fields.Integer(string='Insumos con stock y costo cero', readonly=True)
    inventory_days = fields.Float(string='Días de inventario', readonly=True, digits=(16, 1))
    idle_inventory_value = fields.Monetary(string='Inventario sin movimiento', readonly=True)
    concentration_80_count = fields.Integer(
        string='Productos para el 80% de venta',
        readonly=True,
    )
    top20_sale_share_pct = fields.Float(
        string='Participación del 20% top (%)',
        readonly=True,
        digits=(16, 2),
    )
    q4_low_margin_count = fields.Integer(
        string='Q4 con margen bajo',
        readonly=True,
    )

    origin_line_ids = fields.One2many(
        'bi.business.health.origin.line',
        'health_id',
        string='Crecimiento por origen',
    )
    inventory_line_ids = fields.One2many(
        'bi.business.health.inventory.line',
        'health_id',
        string='Inventario por producto',
    )
    inventory_category_ids = fields.One2many(
        'bi.business.health.inventory.category',
        'health_id',
        string='Inventario por categoría',
    )
    inventory_warehouse_ids = fields.One2many(
        'bi.business.health.inventory.warehouse',
        'health_id',
        string='Inventario por almacén',
    )
    supply_line_ids = fields.One2many(
        'bi.business.health.supply.line',
        'health_id',
        string='Inventario de insumos',
    )
    quartile_ids = fields.One2many(
        'bi.business.health.quartile',
        'health_id',
        string='Cuartiles',
    )
    product_line_ids = fields.One2many(
        'bi.business.health.product.line',
        'health_id',
        string='Detalle de productos',
    )
    detail_group = fields.Selection(
        selection=[
            ('q4', 'Q4'),
            ('q3', 'Q3'),
            ('q2', 'Q2'),
            ('q1', 'Q1'),
            ('new', 'Nuevos'),
            ('no_sale', 'Sin venta'),
            ('comparable', 'Comparables'),
        ],
        string='Grupo en detalle',
    )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        defaults.setdefault('date_from', month_start)
        defaults.setdefault('date_to', month_end)
        defaults.setdefault('company_id', self.env.company.id)
        return defaults

    @api.depends('date_from')
    def _compute_display_name(self):
        for record in self:
            record.display_name = _('Salud del negocio: %s') % (record.date_from or '')

    @api.model
    def action_open(self):
        health = self.create({})
        health._reload_data()
        return {
            'name': _('Salud del negocio'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': health.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    @api.onchange('date_from', 'date_to', 'company_id')
    def _onchange_filters(self):
        self._reload_data()

    def action_previous_month(self):
        self.ensure_one()
        self._set_month_offset(-1)
        return True

    def action_next_month(self):
        self.ensure_one()
        self._set_month_offset(1)
        return True

    def _set_month_offset(self, months):
        base = self.date_from or fields.Date.context_today(self)
        month_start = base.replace(day=1) + relativedelta(months=months)
        month_end = month_start + relativedelta(months=1, days=-1)
        self.write({
            'date_from': month_start,
            'date_to': month_end,
        })
        self._reload_data()

    def _report_timezone(self):
        tz = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        if tz not in pytz.all_timezones_set:
            return 'UTC'
        return tz

    def _period_bounds_utc(self, date_from, date_to):
        """Return UTC datetimes covering [date_from, date_to] in the user timezone."""
        tz = pytz.timezone(self._report_timezone())
        start_local = tz.localize(datetime.combine(date_from, time.min))
        end_local = tz.localize(datetime.combine(date_to, time.max))
        return (
            start_local.astimezone(pytz.UTC).replace(tzinfo=None),
            end_local.astimezone(pytz.UTC).replace(tzinfo=None),
        )

    @staticmethod
    def _growth_pct(current, previous):
        if float_is_zero(previous, precision_digits=6):
            return 0.0
        return (current - previous) / previous * 100.0

    @staticmethod
    def _previous_period(date_from, date_to):
        delta = date_to - date_from
        previous_date_to = date_from - timedelta(days=1)
        previous_date_from = previous_date_to - delta
        return previous_date_from, previous_date_to

    def _clear_data(self):
        self.ensure_one()
        self.previous_date_from = False
        self.previous_date_to = False
        self.sale_amount = 0.0
        self.sale_amount_prev = 0.0
        self.sale_growth_pct = 0.0
        self.qty_sold = 0.0
        self.qty_sold_prev = 0.0
        self.qty_growth_pct = 0.0
        self.order_count = 0
        self.order_count_prev = 0
        self.order_growth_pct = 0.0
        self.avg_ticket = 0.0
        self.avg_ticket_prev = 0.0
        self.avg_ticket_growth_pct = 0.0
        self.cost_amount = 0.0
        self.cost_amount_prev = 0.0
        self.profit_amount = 0.0
        self.profit_amount_prev = 0.0
        self.profit_growth_pct = 0.0
        self.margin_pct = 0.0
        self.margin_pct_prev = 0.0
        self.product_inventory_value = 0.0
        self.supply_inventory_value = 0.0
        self.net_inventory_value = 0.0
        self.zero_cost_product_count = 0
        self.zero_cost_supply_count = 0
        self.inventory_days = 0.0
        self.idle_inventory_value = 0.0
        self.concentration_80_count = 0
        self.top20_sale_share_pct = 0.0
        self.q4_low_margin_count = 0
        self.origin_line_ids = [Command.clear()]
        self.inventory_line_ids = [Command.clear()]
        self.inventory_category_ids = [Command.clear()]
        self.inventory_warehouse_ids = [Command.clear()]
        self.supply_line_ids = [Command.clear()]
        self.quartile_ids = [Command.clear()]
        self.product_line_ids = [Command.clear()]

    def _reload_data(self):
        for health in self:
            if not health.date_from or not health.date_to or not health.company_id:
                health._clear_data()
                continue

            previous_date_from, previous_date_to = self._previous_period(
                health.date_from,
                health.date_to,
            )
            current_rows = health._sale_rows(health.date_from, health.date_to)
            previous_rows = health._sale_rows(previous_date_from, previous_date_to)

            current_totals = health._aggregate_rows(current_rows)
            previous_totals = health._aggregate_rows(previous_rows)

            inventory = health._build_inventory_snapshot()
            sold_product_ids = {
                row.product_id.id
                for row in current_rows
                if row.product_id and not float_is_zero(row.sale_amount, precision_digits=6)
            }
            idle_inventory_value = sum(
                line['value']
                for line in inventory['product_lines']
                if line['product_id'] not in sold_product_ids
            )

            product_stats = health._build_product_stats(current_rows, previous_rows)
            quartile_payload = health._build_quartiles(product_stats, current_totals['sale_amount'])
            concentration = health._concentration(product_stats)

            days = max((health.date_to - health.date_from).days + 1, 1)
            daily_cogs = current_totals['cost_amount'] / days if current_totals['cost_amount'] else 0.0
            inventory_days = (
                inventory['product_inventory_value'] / daily_cogs
                if daily_cogs
                else 0.0
            )

            avg_ticket = (
                current_totals['sale_amount'] / current_totals['order_count']
                if current_totals['order_count']
                else 0.0
            )
            avg_ticket_prev = (
                previous_totals['sale_amount'] / previous_totals['order_count']
                if previous_totals['order_count']
                else 0.0
            )
            margin_pct = (
                current_totals['profit_amount'] / current_totals['sale_amount'] * 100.0
                if current_totals['sale_amount']
                else 0.0
            )
            margin_pct_prev = (
                previous_totals['profit_amount'] / previous_totals['sale_amount'] * 100.0
                if previous_totals['sale_amount']
                else 0.0
            )

            origin_commands = health._origin_commands(
                current_rows,
                previous_rows,
                health.currency_id.id,
            )

            health.previous_date_from = previous_date_from
            health.previous_date_to = previous_date_to
            health.sale_amount = current_totals['sale_amount']
            health.sale_amount_prev = previous_totals['sale_amount']
            health.sale_growth_pct = self._growth_pct(
                current_totals['sale_amount'],
                previous_totals['sale_amount'],
            )
            health.qty_sold = current_totals['qty_sold']
            health.qty_sold_prev = previous_totals['qty_sold']
            health.qty_growth_pct = self._growth_pct(
                current_totals['qty_sold'],
                previous_totals['qty_sold'],
            )
            health.order_count = current_totals['order_count']
            health.order_count_prev = previous_totals['order_count']
            health.order_growth_pct = self._growth_pct(
                current_totals['order_count'],
                previous_totals['order_count'],
            )
            health.avg_ticket = avg_ticket
            health.avg_ticket_prev = avg_ticket_prev
            health.avg_ticket_growth_pct = self._growth_pct(avg_ticket, avg_ticket_prev)
            health.cost_amount = current_totals['cost_amount']
            health.cost_amount_prev = previous_totals['cost_amount']
            health.profit_amount = current_totals['profit_amount']
            health.profit_amount_prev = previous_totals['profit_amount']
            health.profit_growth_pct = self._growth_pct(
                current_totals['profit_amount'],
                previous_totals['profit_amount'],
            )
            health.margin_pct = margin_pct
            health.margin_pct_prev = margin_pct_prev
            health.product_inventory_value = inventory['product_inventory_value']
            health.supply_inventory_value = inventory['supply_inventory_value']
            health.net_inventory_value = inventory['net_inventory_value']
            health.zero_cost_product_count = inventory['zero_cost_product_count']
            health.zero_cost_supply_count = inventory['zero_cost_supply_count']
            health.inventory_days = inventory_days
            health.idle_inventory_value = idle_inventory_value
            health.concentration_80_count = concentration['concentration_80_count']
            health.top20_sale_share_pct = concentration['top20_sale_share_pct']
            health.q4_low_margin_count = quartile_payload['q4_low_margin_count']
            health.origin_line_ids = [Command.clear()] + origin_commands
            health.inventory_line_ids = [Command.clear()] + [
                Command.create(vals) for vals in inventory['product_lines']
            ]
            health.inventory_category_ids = [Command.clear()] + [
                Command.create(vals) for vals in inventory['category_lines']
            ]
            health.inventory_warehouse_ids = [Command.clear()] + [
                Command.create(vals) for vals in inventory['warehouse_lines']
            ]
            health.supply_line_ids = [Command.clear()] + [
                Command.create(vals) for vals in inventory['supply_lines']
            ]
            health.quartile_ids = [Command.clear()] + [
                Command.create(vals) for vals in quartile_payload['quartile_lines']
            ]
            health.product_line_ids = [Command.clear()] + [
                Command.create(vals) for vals in quartile_payload['product_lines']
            ]

    def _sale_rows(self, date_from, date_to):
        self.ensure_one()
        start_utc, end_utc = self._period_bounds_utc(date_from, date_to)
        return self.env['bi.product.sale.report'].search([
            ('company_id', '=', self.company_id.id),
            ('date_order', '>=', start_utc),
            ('date_order', '<=', end_utc),
        ])

    def _aggregate_rows(self, rows):
        order_refs = {row.order_ref for row in rows if row.order_ref}
        sale_amount = sum(rows.mapped('sale_amount'))
        cost_amount = sum(rows.mapped('cost_amount'))
        return {
            'sale_amount': sale_amount,
            'cost_amount': cost_amount,
            'profit_amount': sale_amount - cost_amount,
            'qty_sold': sum(rows.mapped('qty_sold')),
            'order_count': len(order_refs),
        }

    def _origin_commands(self, current_rows, previous_rows, currency_id):
        origins = ['apk', 'pos', 'sale']
        current_by_origin = defaultdict(lambda: {'sale_amount': 0.0, 'qty_sold': 0.0, 'orders': set()})
        previous_by_origin = defaultdict(lambda: {'sale_amount': 0.0, 'qty_sold': 0.0, 'orders': set()})
        for row in current_rows:
            bucket = current_by_origin[row.sale_origin]
            bucket['sale_amount'] += row.sale_amount
            bucket['qty_sold'] += row.qty_sold
            if row.order_ref:
                bucket['orders'].add(row.order_ref)
        for row in previous_rows:
            bucket = previous_by_origin[row.sale_origin]
            bucket['sale_amount'] += row.sale_amount
            bucket['qty_sold'] += row.qty_sold
            if row.order_ref:
                bucket['orders'].add(row.order_ref)

        commands = []
        for origin in origins:
            current = current_by_origin[origin]
            previous = previous_by_origin[origin]
            if (
                float_is_zero(current['sale_amount'], precision_digits=6)
                and float_is_zero(previous['sale_amount'], precision_digits=6)
            ):
                continue
            commands.append(Command.create({
                'sale_origin': origin,
                'currency_id': currency_id,
                'sale_amount': current['sale_amount'],
                'sale_amount_prev': previous['sale_amount'],
                'sale_growth_pct': self._growth_pct(current['sale_amount'], previous['sale_amount']),
                'qty_sold': current['qty_sold'],
                'qty_sold_prev': previous['qty_sold'],
                'order_count': len(current['orders']),
                'order_count_prev': len(previous['orders']),
            }))
        return commands

    def _build_inventory_snapshot(self):
        self.ensure_one()
        company = self.company_id
        currency_id = company.currency_id.id
        Quant = self.env['stock.quant'].with_company(company)

        quants = Quant.search([
            ('company_id', '=', company.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
            ('product_id.is_storable', '=', True),
        ])

        product_qty = defaultdict(float)
        product_warehouse_qty = defaultdict(lambda: defaultdict(float))
        for quant in quants:
            product_qty[quant.product_id.id] += quant.quantity
            warehouse = quant.warehouse_id
            if warehouse:
                product_warehouse_qty[warehouse.id][quant.product_id.id] += quant.quantity

        products = self.env['product.product'].with_company(company).browse(list(product_qty))
        product_map = {product.id: product for product in products}

        product_lines = []
        category_totals = defaultdict(float)
        zero_cost_product_count = 0
        product_inventory_value = 0.0

        for product_id, qty in product_qty.items():
            product = product_map[product_id]
            unit_cost = product.standard_price
            value = qty * unit_cost
            if float_is_zero(unit_cost, precision_digits=6) and not float_is_zero(qty, precision_digits=6):
                zero_cost_product_count += 1
            product_inventory_value += value
            categ_id = product.categ_id.id
            category_totals[categ_id] += value
            product_lines.append({
                'product_id': product_id,
                'categ_id': categ_id,
                'currency_id': currency_id,
                'quantity': qty,
                'unit_cost': unit_cost,
                'value': value,
                'zero_cost': float_is_zero(unit_cost, precision_digits=6),
            })

        product_lines.sort(key=lambda line: line['value'], reverse=True)

        category_lines = []
        for categ_id, value in sorted(category_totals.items(), key=lambda item: item[1], reverse=True):
            share = (
                value / product_inventory_value * 100.0
                if product_inventory_value
                else 0.0
            )
            category_lines.append({
                'categ_id': categ_id,
                'currency_id': currency_id,
                'value': value,
                'share_pct': share,
            })

        warehouse_lines = []
        for warehouse_id, qty_by_product in product_warehouse_qty.items():
            value = 0.0
            for product_id, qty in qty_by_product.items():
                product = product_map.get(product_id)
                if not product:
                    continue
                value += qty * product.standard_price
            warehouse_lines.append({
                'warehouse_id': warehouse_id,
                'currency_id': currency_id,
                'value': value,
            })
        warehouse_lines.sort(key=lambda line: line['value'], reverse=True)

        supplies = self.env['bi.supply'].search([
            ('company_id', '=', company.id),
            ('qty_available', '>', 0),
        ])
        supply_lines = []
        supply_inventory_value = 0.0
        zero_cost_supply_count = 0
        for supply in supplies:
            value = supply.qty_available * supply.average_cost
            supply_inventory_value += value
            if float_is_zero(supply.average_cost, precision_digits=6):
                zero_cost_supply_count += 1
            supply_lines.append({
                'supply_id': supply.id,
                'currency_id': currency_id,
                'quantity': supply.qty_available,
                'unit_cost': supply.average_cost,
                'value': value,
                'zero_cost': float_is_zero(supply.average_cost, precision_digits=6),
            })
        supply_lines.sort(key=lambda line: line['value'], reverse=True)

        return {
            'product_inventory_value': product_inventory_value,
            'supply_inventory_value': supply_inventory_value,
            'net_inventory_value': product_inventory_value + supply_inventory_value,
            'zero_cost_product_count': zero_cost_product_count,
            'zero_cost_supply_count': zero_cost_supply_count,
            'product_lines': product_lines,
            'category_lines': category_lines,
            'warehouse_lines': warehouse_lines,
            'supply_lines': supply_lines,
        }

    def _build_product_stats(self, current_rows, previous_rows):
        stats = {}

        def ensure(product):
            key = product.id
            if key not in stats:
                stats[key] = {
                    'product_id': product.id,
                    'categ_id': product.categ_id.id,
                    'sale_amount': 0.0,
                    'sale_amount_prev': 0.0,
                    'qty_sold': 0.0,
                    'qty_sold_prev': 0.0,
                    'cost_amount': 0.0,
                    'cost_amount_prev': 0.0,
                }
            return stats[key]

        for row in current_rows:
            if not row.product_id:
                continue
            bucket = ensure(row.product_id)
            bucket['sale_amount'] += row.sale_amount
            bucket['qty_sold'] += row.qty_sold
            bucket['cost_amount'] += row.cost_amount

        for row in previous_rows:
            if not row.product_id:
                continue
            bucket = ensure(row.product_id)
            bucket['sale_amount_prev'] += row.sale_amount
            bucket['qty_sold_prev'] += row.qty_sold
            bucket['cost_amount_prev'] += row.cost_amount

        for bucket in stats.values():
            bucket['profit_amount'] = bucket['sale_amount'] - bucket['cost_amount']
            bucket['margin_pct'] = (
                bucket['profit_amount'] / bucket['sale_amount'] * 100.0
                if bucket['sale_amount']
                else 0.0
            )
            if bucket['sale_amount_prev'] > 0 and bucket['sale_amount'] > 0:
                bucket['group_kind'] = 'comparable'
                bucket['growth_pct'] = self._growth_pct(
                    bucket['sale_amount'],
                    bucket['sale_amount_prev'],
                )
            elif bucket['sale_amount'] > 0 and float_is_zero(bucket['sale_amount_prev'], precision_digits=6):
                bucket['group_kind'] = 'new'
                bucket['growth_pct'] = 0.0
            elif bucket['sale_amount_prev'] > 0 and float_is_zero(bucket['sale_amount'], precision_digits=6):
                bucket['group_kind'] = 'no_sale'
                bucket['growth_pct'] = -100.0
            else:
                bucket['group_kind'] = False
                bucket['growth_pct'] = 0.0
        return stats

    def _build_quartiles(self, product_stats, total_sale_amount):
        currency_id = self.company_id.currency_id.id
        comparable = [
            stats for stats in product_stats.values()
            if stats['group_kind'] == 'comparable'
        ]
        comparable.sort(key=lambda item: item['growth_pct'])
        force_quartiles = len(comparable) >= 4

        for index, stats in enumerate(comparable):
            if force_quartiles:
                quartile_number = (index * 4) // len(comparable) + 1
                stats['group'] = f'q{quartile_number}'
            else:
                stats['group'] = 'comparable'

        for stats in product_stats.values():
            if stats['group_kind'] == 'new':
                stats['group'] = 'new'
            elif stats['group_kind'] == 'no_sale':
                stats['group'] = 'no_sale'
            elif stats['group_kind'] != 'comparable':
                stats['group'] = False

        group_order = ['q4', 'q3', 'q2', 'q1', 'new', 'no_sale', 'comparable']
        grouped = defaultdict(list)
        for stats in product_stats.values():
            if stats.get('group'):
                grouped[stats['group']].append(stats)

        quartile_lines = []
        for group in group_order:
            items = grouped.get(group)
            if not items:
                continue
            sale_amount = sum(item['sale_amount'] for item in items)
            sale_amount_prev = sum(item['sale_amount_prev'] for item in items)
            growth_values = [
                item['growth_pct']
                for item in items
                if item['group_kind'] == 'comparable'
            ]
            median_growth = statistics.median(growth_values) if growth_values else 0.0
            share_pct = (
                sale_amount / total_sale_amount * 100.0
                if total_sale_amount
                else 0.0
            )
            quartile_lines.append({
                'group': group,
                'currency_id': currency_id,
                'product_count': len(items),
                'sale_amount': sale_amount,
                'sale_amount_prev': sale_amount_prev,
                'sale_variation': sale_amount - sale_amount_prev,
                'median_growth_pct': median_growth,
                'share_pct': share_pct,
            })

        q4_low_margin_count = sum(
            1
            for item in grouped.get('q4', [])
            if item['margin_pct'] < 10.0
        )

        product_lines = []
        for stats in sorted(
            product_stats.values(),
            key=lambda item: (
                group_order.index(item['group']) if item.get('group') in group_order else 99,
                -item['growth_pct'],
                -item['sale_amount'],
            ),
        ):
            if not stats.get('group'):
                continue
            product_lines.append({
                'product_id': stats['product_id'],
                'categ_id': stats['categ_id'],
                'currency_id': currency_id,
                'group': stats['group'],
                'sale_amount': stats['sale_amount'],
                'sale_amount_prev': stats['sale_amount_prev'],
                'growth_pct': stats['growth_pct'],
                'qty_sold': stats['qty_sold'],
                'profit_amount': stats['profit_amount'],
                'margin_pct': stats['margin_pct'],
                'low_margin': stats['group'] == 'q4' and stats['margin_pct'] < 10.0,
            })

        return {
            'quartile_lines': quartile_lines,
            'product_lines': product_lines,
            'q4_low_margin_count': q4_low_margin_count,
        }

    def _concentration(self, product_stats):
        current_products = [
            stats for stats in product_stats.values()
            if stats['sale_amount'] > 0
        ]
        current_products.sort(key=lambda item: item['sale_amount'], reverse=True)
        total_sale = sum(item['sale_amount'] for item in current_products)
        if not current_products or float_is_zero(total_sale, precision_digits=6):
            return {
                'concentration_80_count': 0,
                'top20_sale_share_pct': 0.0,
            }

        cumulative = 0.0
        concentration_80_count = 0
        for item in current_products:
            cumulative += item['sale_amount']
            concentration_80_count += 1
            if cumulative >= total_sale * 0.8:
                break

        top_count = max(int(len(current_products) * 0.2 + 0.999999), 1)
        top_sale = sum(item['sale_amount'] for item in current_products[:top_count])
        return {
            'concentration_80_count': concentration_80_count,
            'top20_sale_share_pct': top_sale / total_sale * 100.0,
        }


class BiBusinessHealthOriginLine(models.TransientModel):
    _name = 'bi.business.health.origin.line'
    _description = 'Crecimiento por origen'
    _order = 'sale_amount desc'

    health_id = fields.Many2one(
        'bi.business.health',
        string='Salud del negocio',
        required=True,
        ondelete='cascade',
    )
    sale_origin = fields.Selection(
        selection=[
            ('apk', 'Apk'),
            ('pos', 'POS'),
            ('sale', 'Venta'),
        ],
        string='Origen de venta',
        readonly=True,
    )
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    sale_amount = fields.Monetary(string='Importe de venta', readonly=True)
    sale_amount_prev = fields.Monetary(string='Venta periodo anterior', readonly=True)
    sale_growth_pct = fields.Float(string='Crecimiento (%)', readonly=True, digits=(16, 2))
    qty_sold = fields.Float(string='Unidades', readonly=True, digits='Product Unit')
    qty_sold_prev = fields.Float(string='Unidades anteriores', readonly=True, digits='Product Unit')
    order_count = fields.Integer(string='Pedidos', readonly=True)
    order_count_prev = fields.Integer(string='Pedidos anteriores', readonly=True)


class BiBusinessHealthInventoryLine(models.TransientModel):
    _name = 'bi.business.health.inventory.line'
    _description = 'Inventario por producto'
    _order = 'value desc'

    health_id = fields.Many2one(
        'bi.business.health',
        string='Salud del negocio',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    categ_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    quantity = fields.Float(string='Cantidad', readonly=True, digits='Product Unit')
    unit_cost = fields.Monetary(string='Costo unitario', readonly=True)
    value = fields.Monetary(string='Valor', readonly=True)
    zero_cost = fields.Boolean(string='Costo cero', readonly=True)


class BiBusinessHealthInventoryCategory(models.TransientModel):
    _name = 'bi.business.health.inventory.category'
    _description = 'Inventario por categoría'
    _order = 'value desc'

    health_id = fields.Many2one(
        'bi.business.health',
        string='Salud del negocio',
        required=True,
        ondelete='cascade',
    )
    categ_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    value = fields.Monetary(string='Valor', readonly=True)
    share_pct = fields.Float(string='Participación (%)', readonly=True, digits=(16, 2))


class BiBusinessHealthInventoryWarehouse(models.TransientModel):
    _name = 'bi.business.health.inventory.warehouse'
    _description = 'Inventario por almacén'
    _order = 'value desc'

    health_id = fields.Many2one(
        'bi.business.health',
        string='Salud del negocio',
        required=True,
        ondelete='cascade',
    )
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    value = fields.Monetary(string='Valor', readonly=True)


class BiBusinessHealthSupplyLine(models.TransientModel):
    _name = 'bi.business.health.supply.line'
    _description = 'Inventario de insumos'
    _order = 'value desc'

    health_id = fields.Many2one(
        'bi.business.health',
        string='Salud del negocio',
        required=True,
        ondelete='cascade',
    )
    supply_id = fields.Many2one('bi.supply', string='Insumo', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    quantity = fields.Float(string='Cantidad', readonly=True, digits='Product Unit')
    unit_cost = fields.Monetary(string='Costo promedio', readonly=True)
    value = fields.Monetary(string='Valor', readonly=True)
    zero_cost = fields.Boolean(string='Costo cero', readonly=True)


class BiBusinessHealthQuartile(models.TransientModel):
    _name = 'bi.business.health.quartile'
    _description = 'Cuartil de crecimiento'
    _order = 'sequence asc'

    health_id = fields.Many2one(
        'bi.business.health',
        string='Salud del negocio',
        required=True,
        ondelete='cascade',
    )
    group = fields.Selection(
        selection=[
            ('q4', 'Q4'),
            ('q3', 'Q3'),
            ('q2', 'Q2'),
            ('q1', 'Q1'),
            ('new', 'Nuevos'),
            ('no_sale', 'Sin venta'),
            ('comparable', 'Comparables'),
        ],
        string='Grupo',
        readonly=True,
    )
    sequence = fields.Integer(compute='_compute_sequence', store=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    product_count = fields.Integer(string='Productos', readonly=True)
    sale_amount = fields.Monetary(string='Venta periodo', readonly=True)
    sale_amount_prev = fields.Monetary(string='Venta anterior', readonly=True)
    sale_variation = fields.Monetary(string='Variación', readonly=True)
    median_growth_pct = fields.Float(string='Mediana de crecimiento (%)', readonly=True, digits=(16, 2))
    share_pct = fields.Float(string='Participación (%)', readonly=True, digits=(16, 2))

    @api.depends('group')
    def _compute_sequence(self):
        order = {
            'q4': 10,
            'q3': 20,
            'q2': 30,
            'q1': 40,
            'new': 50,
            'no_sale': 60,
            'comparable': 70,
        }
        for line in self:
            line.sequence = order.get(line.group, 100)

    def action_show_in_detail(self):
        self.ensure_one()
        self.health_id.detail_group = self.group
        return {
            'name': _('Salud del negocio'),
            'type': 'ir.actions.act_window',
            'res_model': 'bi.business.health',
            'res_id': self.health_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }


class BiBusinessHealthProductLine(models.TransientModel):
    _name = 'bi.business.health.product.line'
    _description = 'Detalle de producto en salud del negocio'
    _order = 'growth_pct desc, sale_amount desc'

    health_id = fields.Many2one(
        'bi.business.health',
        string='Salud del negocio',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    categ_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    group = fields.Selection(
        selection=[
            ('q4', 'Q4'),
            ('q3', 'Q3'),
            ('q2', 'Q2'),
            ('q1', 'Q1'),
            ('new', 'Nuevos'),
            ('no_sale', 'Sin venta'),
            ('comparable', 'Comparables'),
        ],
        string='Grupo',
        readonly=True,
    )
    sale_amount = fields.Monetary(string='Venta periodo', readonly=True)
    sale_amount_prev = fields.Monetary(string='Venta anterior', readonly=True)
    growth_pct = fields.Float(string='Crecimiento (%)', readonly=True, digits=(16, 2))
    qty_sold = fields.Float(string='Unidades', readonly=True, digits='Product Unit')
    profit_amount = fields.Monetary(string='Ganancia', readonly=True)
    margin_pct = fields.Float(string='Margen (%)', readonly=True, digits=(16, 2))
    low_margin = fields.Boolean(string='Margen bajo', readonly=True)
