# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Legacy devices without company_id must be backfilled so the backend list still shows them."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.hooks import backfill_order_bridge_company_ids


@tagged('post_install', '-at_install')
class TestBackfillOrderBridgeCompanyIds(TransactionCase):
    def test_backfill_assigns_main_company_on_null_device_and_partner(self):
        company = self.env.ref('base.main_company')
        partner = self.env['res.partner'].create({
            'name': 'Legacy APK partner',
            'company_id': False,
        })
        device = self.env['order_bridge.device'].create({
            'device_key': 'legacy-device-key',
            'partner_id': partner.id,
            'company_id': company.id,
            'phone': '60000099',
            'phone_validated': False,
            'active': True,
        })
        self.env.cr.execute(
            'UPDATE order_bridge_device SET company_id = NULL WHERE id = %s',
            [device.id],
        )
        self.env.cr.execute(
            'UPDATE res_partner SET company_id = NULL WHERE id = %s',
            [partner.id],
        )
        device.invalidate_recordset(['company_id'])
        partner.invalidate_recordset(['company_id'])
        self.assertFalse(device.company_id)
        self.assertFalse(partner.company_id)

        count = backfill_order_bridge_company_ids(self.env)
        self.assertGreaterEqual(count, 1)

        device.invalidate_recordset(['company_id'])
        partner.invalidate_recordset(['company_id'])
        self.assertEqual(device.company_id, company)
        self.assertEqual(partner.company_id, company)

        self.assertIn(
            device,
            self.env['order_bridge.device'].search([
                ('phone_validated', '=', False),
                ('active', '=', True),
            ]),
        )
