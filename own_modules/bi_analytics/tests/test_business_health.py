# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBiBusinessHealth(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'BI Health Test Co',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'BI Health Customer',
            'company_id': cls.company.id,
        })
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)],
            limit=1,
        )
        cls.products = cls.env['product.product']
        for index in range(1, 5):
            product = cls.env['product.product'].with_company(cls.company).create({
                'name': f'BI Health Product {index}',
                'sale_ok': True,
                'is_storable': True,
                'list_price': 20.0,
                'standard_price': 5.0 * index,
            })
            cls.products |= product
            cls.env['stock.quant'].with_company(cls.company).with_context(
                inventory_mode=True,
            ).create({
                'product_id': product.id,
                'location_id': cls.warehouse.lot_stock_id.id,
                'inventory_quantity': 10.0 * index,
            }).action_apply_inventory()

        cls.zero_cost_product = cls.env['product.product'].with_company(cls.company).create({
            'name': 'BI Health Zero Cost',
            'sale_ok': True,
            'is_storable': True,
            'list_price': 8.0,
            'standard_price': 0.0,
        })
        cls.env['stock.quant'].with_company(cls.company).with_context(
            inventory_mode=True,
        ).create({
            'product_id': cls.zero_cost_product.id,
            'location_id': cls.warehouse.lot_stock_id.id,
            'inventory_quantity': 7.0,
        }).action_apply_inventory()

        cls.new_product = cls.env['product.product'].with_company(cls.company).create({
            'name': 'BI Health New Product',
            'sale_ok': True,
            'list_price': 15.0,
            'standard_price': 3.0,
        })
        cls.no_sale_product = cls.env['product.product'].with_company(cls.company).create({
            'name': 'BI Health No Sale Product',
            'sale_ok': True,
            'list_price': 12.0,
            'standard_price': 2.0,
        })

        cls.supply = cls.env['bi.supply'].with_company(cls.company).create({
            'name': 'BI Health Supply',
            'unit': 'kg',
            'company_id': cls.company.id,
            'currency_id': cls.company.currency_id.id,
        })
        cls.env['bi.supply.entry'].create({
            'supply_id': cls.supply.id,
            'date': fields.Date.today(),
            'quantity': 20.0,
            'unit_cost': 2.5,
            'company_id': cls.company.id,
            'currency_id': cls.company.currency_id.id,
        })

        today = fields.Date.context_today(cls.env.user)
        cls.date_from = today.replace(day=1)
        cls.date_to = cls.date_from + relativedelta(months=1, days=-1)
        cls.prev_date_to = cls.date_from - relativedelta(days=1)
        cls.prev_date_from = cls.prev_date_to - (cls.date_to - cls.date_from)

        # Previous period sales: growth ranks P1 < P2 < P3 < P4 after comparing to current.
        # prev amounts: 100, 80, 50, 40
        # current amounts: 90, 100, 120, 200  => growth -10%, +25%, +140%, +400%
        prev_amounts = [100.0, 80.0, 50.0, 40.0]
        current_amounts = [90.0, 100.0, 120.0, 200.0]
        for product, amount in zip(cls.products, prev_amounts):
            cls._create_confirmed_order_cls(product, qty=1, price_unit=amount, date_order=cls._dt(cls.prev_date_from))
        for product, amount in zip(cls.products, current_amounts):
            cls._create_confirmed_order_cls(product, qty=1, price_unit=amount, date_order=cls._dt(cls.date_from))

        cls._create_confirmed_order_cls(
            cls.new_product,
            qty=1,
            price_unit=50.0,
            date_order=cls._dt(cls.date_from),
        )
        cls._create_confirmed_order_cls(
            cls.no_sale_product,
            qty=1,
            price_unit=30.0,
            date_order=cls._dt(cls.prev_date_from),
        )

    @classmethod
    def _dt(cls, day):
        return fields.Datetime.to_datetime(datetime.combine(day, datetime.min.time().replace(hour=12)))

    @classmethod
    def _create_confirmed_order_cls(cls, product, qty, price_unit, date_order=None):
        order = cls.env['sale.order'].with_company(cls.company).create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
            })],
        })
        order.action_confirm()
        if date_order:
            order.date_order = date_order
        return order

    def _open_health(self):
        health = self.env['bi.business.health'].with_company(self.company).create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.company.id,
        })
        health._reload_data()
        return health

    def test_net_inventory_value_products_and_supplies(self):
        health = self._open_health()
        # Products 1..4: 10*5 + 20*10 + 30*15 + 40*20 = 50+200+450+800 = 1500
        # Zero-cost product: 7 * 0 = 0
        # Supply: 20 * 2.5 = 50
        self.assertAlmostEqual(health.product_inventory_value, 1500.0)
        self.assertAlmostEqual(health.supply_inventory_value, 50.0)
        self.assertAlmostEqual(health.net_inventory_value, 1550.0)
        self.assertEqual(health.zero_cost_product_count, 1)
        self.assertEqual(health.zero_cost_supply_count, 0)
        self.assertTrue(health.inventory_line_ids)
        self.assertTrue(health.supply_line_ids)
        self.assertTrue(health.inventory_category_ids)
        self.assertTrue(health.inventory_warehouse_ids)

    def test_new_and_no_sale_outside_quartiles(self):
        health = self._open_health()
        groups = {line.group: line for line in health.quartile_ids}
        self.assertIn('new', groups)
        self.assertIn('no_sale', groups)
        self.assertEqual(groups['new'].product_count, 1)
        self.assertEqual(groups['no_sale'].product_count, 1)

        new_lines = health.product_line_ids.filtered(lambda line: line.group == 'new')
        no_sale_lines = health.product_line_ids.filtered(lambda line: line.group == 'no_sale')
        self.assertEqual(new_lines.product_id, self.new_product)
        self.assertEqual(no_sale_lines.product_id, self.no_sale_product)

        for quartile in ('q1', 'q2', 'q3', 'q4'):
            quartile_products = health.product_line_ids.filtered(
                lambda line, q=quartile: line.group == q,
            ).mapped('product_id')
            self.assertNotIn(self.new_product, quartile_products)
            self.assertNotIn(self.no_sale_product, quartile_products)

    def test_quartile_partition_by_growth(self):
        health = self._open_health()
        # With 4 comparable products, each quartile has exactly one.
        for quartile in ('q1', 'q2', 'q3', 'q4'):
            lines = health.product_line_ids.filtered(lambda line, q=quartile: line.group == q)
            self.assertEqual(len(lines), 1, quartile)

        q1 = health.product_line_ids.filtered(lambda line: line.group == 'q1')
        q4 = health.product_line_ids.filtered(lambda line: line.group == 'q4')
        self.assertEqual(q1.product_id, self.products[0])
        self.assertEqual(q4.product_id, self.products[3])
        self.assertLess(q1.growth_pct, q4.growth_pct)

        quartile_cards = {line.group: line for line in health.quartile_ids}
        self.assertAlmostEqual(quartile_cards['q4'].median_growth_pct, q4.growth_pct)
        self.assertAlmostEqual(quartile_cards['q1'].median_growth_pct, q1.growth_pct)

    def test_fewer_than_four_comparable_skips_forced_quartiles(self):
        company_b = self.env['res.company'].create({'name': 'BI Health Solo Co'})
        partner_b = self.env['res.partner'].create({
            'name': 'BI Health Solo Customer',
            'company_id': company_b.id,
        })
        lonely = self.env['product.product'].with_company(company_b).create({
            'name': 'BI Health Lonely',
            'sale_ok': True,
            'list_price': 10.0,
            'standard_price': 1.0,
            'company_id': company_b.id,
        })
        for price, day in ((10.0, self.prev_date_from), (20.0, self.date_from)):
            order = self.env['sale.order'].with_company(company_b).create({
                'partner_id': partner_b.id,
                'order_line': [(0, 0, {
                    'product_id': lonely.id,
                    'product_uom_qty': 1,
                    'price_unit': price,
                })],
            })
            order.action_confirm()
            order.date_order = self._dt(day)

        health = self.env['bi.business.health'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': company_b.id,
        })
        health._reload_data()
        self.assertFalse(health.product_line_ids.filtered(lambda line: line.group in ('q1', 'q2', 'q3', 'q4')))
        comparable = health.product_line_ids.filtered(lambda line: line.group == 'comparable')
        self.assertEqual(len(comparable), 1)
        self.assertEqual(comparable.product_id, lonely)

    def test_global_growth_and_action_open(self):
        action = self.env['bi.business.health'].with_company(self.company).action_open()
        self.assertEqual(action['res_model'], 'bi.business.health')
        health = self.env['bi.business.health'].browse(action['res_id'])
        health.write({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.company.id,
        })
        health._reload_data()
        # Current sales: 90+100+120+200+50 = 560
        # Previous sales: 100+80+50+40+30 = 300
        self.assertAlmostEqual(health.sale_amount, 560.0)
        self.assertAlmostEqual(health.sale_amount_prev, 300.0)
        self.assertAlmostEqual(
            health.sale_growth_pct,
            (560.0 - 300.0) / 300.0 * 100.0,
            places=2,
        )
        self.assertTrue(health.origin_line_ids)
        self.assertGreater(health.concentration_80_count, 0)
