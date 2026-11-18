# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.schemas.bodies import RegisterBody
from odoo.addons.order_bridge.utils.phone_match import (
    canonical_registration_phone,
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

    def test_canonical_registration_phone(self):
        self.assertEqual(canonical_registration_phone('53024637'), '+5353024637')
        self.assertEqual(canonical_registration_phone('+5353024637'), '+5353024637')
        self.assertEqual(canonical_registration_phone('+12025551234'), '+12025551234')
        self.assertEqual(canonical_registration_phone(''), '')
        self.assertEqual(canonical_registration_phone(None), '')
        self.assertEqual(canonical_registration_phone('+53 5302-4637'), '')
        self.assertEqual(canonical_registration_phone('5353024637'), '')
        self.assertEqual(canonical_registration_phone('005353024637'), '')
        self.assertEqual(canonical_registration_phone('+535302463'), '')
        self.assertEqual(canonical_registration_phone('+53530246370'), '')

    def test_register_body_phone_validator(self):
        self.assertEqual(
            RegisterBody(device_key='k', phone='53024637').phone,
            '+5353024637',
        )
        self.assertEqual(
            RegisterBody(device_key='k', phone='+5353024637').phone,
            '+5353024637',
        )
        self.assertEqual(
            RegisterBody(device_key='k', phone='+12025551234').phone,
            '+12025551234',
        )
        with self.assertRaises(Exception):
            RegisterBody(device_key='k', phone='5353024637')
        with self.assertRaises(Exception):
            RegisterBody(device_key='k', phone='+53 5302-4637')
        with self.assertRaises(Exception):
            RegisterBody(device_key='k', phone='005353024637')

    def test_register_or_get_merges_legacy_and_e164(self):
        Device = self.env['order_bridge.device'].sudo()
        company = self.env.company
        first = Device.register_or_get('53024637', 'phone-legacy-key', company=company)
        self.assertEqual(first['device'].phone, '+5353024637')
        self.assertEqual(first['partner'].phone, '+5353024637')
        self.assertEqual(first['partner'].name, '+5353024637')

        second = Device.register_or_get(
            '+5353024637', 'phone-e164-key', company=company, app_version='1.0.0 web',
        )
        self.assertEqual(second['partner'], first['partner'])
        self.assertEqual(second['device'].phone, '+5353024637')
        self.assertEqual(second['partner'].phone, '+5353024637')

    def test_find_customer_rewrites_legacy_eight_digit_phone(self):
        Partner = self.env['res.partner'].sudo()
        Device = self.env['order_bridge.device'].sudo()
        company = self.env.company
        partner = Partner.create({
            'name': '59001122',
            'phone': '59001122',
            'company_id': company.id,
        })
        self.assertEqual(partner.order_bridge_phone_key, '59001122')
        result = Device.register_or_get('+5359001122', 'phone-rewrite-key', company=company)
        partner.invalidate_recordset()
        self.assertEqual(result['partner'], partner)
        self.assertEqual(partner.phone, '+5359001122')
        self.assertEqual(partner.name, '+5359001122')

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
