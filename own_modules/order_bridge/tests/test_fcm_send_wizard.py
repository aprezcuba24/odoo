# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderBridgeFcmSendWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'FCM wizard test contact'})
        cls.device = cls.env['order_bridge.device'].create({
            'device_key': 'fcm-wizard-test-device',
            'partner_id': cls.partner.id,
            'phone': '60000001',
        })
        now = fields.Datetime.now()
        cls.env['order_bridge.push_token'].create({
            'device_id': cls.device.id,
            'fcm_token': 'a' * 32,
            'platform': 'android',
            'last_seen_at': now,
        })

    def _new_wizard(self, **kwargs):
        return self.env['order_bridge.fcm.send.wizard'].create(
            {
                'target_mode': 'single_partner',
                'partner_id': self.partner.id,
                'title': 'T',
                'body': 'B',
                **kwargs,
            }
        )

    @patch('odoo.addons.order_bridge.utils.fcm_client.send_notification_multicast', return_value=[])
    @patch('odoo.addons.order_bridge.utils.fcm_client.ensure_firebase_app')
    def test_wizard_single_partner_sends(self, _mock_ensure, mock_multi):
        w = self._new_wizard()
        w.action_send()
        mock_multi.assert_called()
        _call = mock_multi.call_args[0]
        self.assertIn('a' * 32, _call[0])

    @patch('odoo.addons.order_bridge.utils.fcm_client.send_to_topic', return_value='mid')
    @patch('odoo.addons.order_bridge.utils.fcm_client.ensure_firebase_app')
    def test_wizard_topic_sends(self, _mock_ensure, mock_topic):
        w = self.env['order_bridge.fcm.send.wizard'].create({
            'target_mode': 'topic',
            'fcm_topic': 'com_culabs_odooshop_all',
            'title': 'Camp',
            'body': 'Body',
        })
        w.action_send()
        mock_topic.assert_called_once()
        self.assertEqual(mock_topic.call_args[0][0], 'com_culabs_odooshop_all')

    def test_wizard_topic_invalid_name(self):
        w = self.env['order_bridge.fcm.send.wizard'].create({
            'target_mode': 'topic',
            'fcm_topic': 'bad topic',
            'title': 'T',
            'body': 'B',
        })
        with self.assertRaises(UserError):
            w.action_send()

    def test_wizard_data_json_not_object(self):
        w = self._new_wizard(data_json='[1,2,3]')
        with self.assertRaises(UserError):
            w.action_send()

    def test_default_get_multi_from_list_context(self):
        p2 = self.env['res.partner'].create({'name': 'P2 FCM test'})
        Wizard = self.env['order_bridge.fcm.send.wizard'].with_context(
            active_model='res.partner',
            active_ids=(self.partner + p2).ids,
        )
        vals = Wizard.default_get(list(Wizard._fields))
        self.assertEqual(vals.get('target_mode'), 'multi_partner')
        # partners order may differ; set comparison
        self.assertSetEqual(
            set(vals['partner_ids'][0][2]),
            {self.partner.id, p2.id},
        )

    def test_default_get_respects_form_single(self):
        Wizard = self.env['order_bridge.fcm.send.wizard'].with_context(
            default_target_mode='single_partner',
            default_partner_id=self.partner.id,
            active_model='res.partner',
            active_ids=[self.partner.id],
        )
        vals = Wizard.default_get(list(Wizard._fields))
        self.assertEqual(vals.get('target_mode'), 'single_partner')
        self.assertEqual(vals.get('partner_id'), self.partner.id)

    def test_fcm_portal_cannot_send(self):
        group_portal = self.env.ref('base.group_portal')
        portal_user = self.env['res.users'].create(
            {
                'name': 'Portal FCM test',
                'login': 'portal_fcm_wizard_test',
                'group_ids': [Command.set([group_portal.id])],
            }
        )
        fcm = self.env['order_bridge.fcm'].with_user(portal_user)
        with self.assertRaises(AccessError):
            fcm.send_to_partner(self.partner.id, 't', 'b')
