# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Normalize stored phones to compact E.164 (legacy 8 digits → ``+53…``)."""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.order_bridge.utils.phone_match import canonical_registration_phone

_logger = logging.getLogger(__name__)


def _rewrite_phone_fields(records, phone_field='phone', also_rename_when_name_is_phone=False):
    for record in records:
        old = (record[phone_field] or '').strip()
        if not old:
            continue
        new = canonical_registration_phone(old)
        if not new or new == old:
            continue
        vals = {phone_field: new}
        if also_rename_when_name_is_phone and (record.name or '').strip() == old:
            vals['name'] = new
        record.write(vals)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Device = env['order_bridge.device'].sudo()
    Partner = env['res.partner'].sudo()
    Snapshot = env['order_bridge.order_address_snapshot'].sudo()

    devices = Device.search([('phone', '!=', False)])
    partners = Partner.search([('phone', '!=', False)])
    snapshots = Snapshot.search([('phone', '!=', False)])

    _rewrite_phone_fields(devices)
    _rewrite_phone_fields(partners, also_rename_when_name_is_phone=True)
    _rewrite_phone_fields(snapshots)

    _logger.info(
        'order_bridge phone canonicalization: devices=%s partners=%s snapshots=%s',
        len(devices),
        len(partners),
        len(snapshots),
    )
