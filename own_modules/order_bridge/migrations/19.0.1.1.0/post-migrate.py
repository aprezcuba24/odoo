# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Backfill company_id on devices created before the multi-company field existed."""

from odoo import SUPERUSER_ID, api

from odoo.addons.order_bridge.hooks import backfill_order_bridge_company_ids


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    backfill_order_bridge_company_ids(env)
