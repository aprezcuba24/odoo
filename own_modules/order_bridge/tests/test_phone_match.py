# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.utils.phone_match import (
    phone_digits,
    phone_match_domain,
    phone_match_key,
)


@tagged('post_install', '-at_install')
class TestPhoneMatch(TransactionCase):
    def test_phone_match_key_cuba_equivalents(self):
        self.assertEqual(phone_match_key('53024637'), '53024637')
        self.assertEqual(phone_match_key('5353024637'), '53024637')
        self.assertEqual(phone_match_key('+53 5302-4637'), '53024637')
        self.assertEqual(phone_match_key('005353024637'), '53024637')
        self.assertEqual(phone_match_key(' 53024637 '), '53024637')

    def test_phone_match_key_other_numbers(self):
        self.assertEqual(phone_match_key('+529991110001'), '529991110001')
        self.assertEqual(phone_match_key('00 52 999 111 0001'), '529991110001')
        self.assertEqual(phone_match_key(''), '')
        self.assertEqual(phone_match_key(None), '')
        self.assertEqual(phone_digits('+53 5302-4637'), '5353024637')

    def test_phone_match_domain(self):
        self.assertEqual(
            phone_match_domain('5353024637'),
            [('order_bridge_phone_key', '=', '53024637')],
        )
        self.assertEqual(phone_match_domain(''), [('id', '=', False)])

    def test_partner_phone_key_and_search(self):
        partner = self.env['res.partner'].create({
            'name': 'Cliente CU',
            'phone': '+5353024637',
        })
        self.assertEqual(partner.order_bridge_phone_key, '53024637')

        found = self.env['res.partner'].search([
            ('phone_mobile_search', '=', '53024637'),
            ('id', '=', partner.id),
        ])
        self.assertIn(partner, found)

        found_intl = self.env['res.partner'].search([
            ('phone_mobile_search', '=', '5353024637'),
            ('id', '=', partner.id),
        ])
        self.assertIn(partner, found_intl)
