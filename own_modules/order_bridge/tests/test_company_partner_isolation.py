# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCompanyPartnerIsolation(TransactionCase):
    """Shop phone must not bind app devices to res.company.partner_id."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company_name = 'El Brando Shop'
        cls.shop_phone = '5551234567'
        cls.company.write({
            'name': cls.company_name,
            'phone': cls.shop_phone,
        })
        cls.Device = cls.env['order_bridge.device'].sudo()
        cls.PartnerAddress = cls.env['order_bridge.partner_address'].sudo()
        cls.Municipality = cls.env['order_bridge.municipality'].sudo()
        cls.Neighborhood = cls.env['order_bridge.neighborhood'].sudo()

    def test_register_with_shop_phone_creates_person_partner(self):
        result = self.Device.register_or_get(
            self.shop_phone,
            'device-shop-phone-new',
            company=self.company,
        )
        partner = result['partner']
        self.assertNotEqual(partner, self.company.partner_id)
        self.assertFalse(partner._order_bridge_is_system_partner())
        self.assertEqual(self.company.name, self.company_name)
        self.assertEqual(result['device'].partner_id, partner)

    def test_profile_put_does_not_rename_company(self):
        result = self.Device.register_or_get(
            self.shop_phone,
            'device-shop-phone-profile',
            company=self.company,
        )
        partner = result['partner']
        municipality = self.Municipality.create({'name': 'Mun Isolation'})
        neighborhood = self.Neighborhood.create({
            'name': 'Bar Isolation',
            'municipality_id': municipality.id,
        })
        updated = self.PartnerAddress.order_bridge_put_full(
            partner,
            'Renier Ricardo Figueredo',
            street='Calle 1',
            neighborhood_id=neighborhood.id,
            municipality_id=municipality.id,
            state='Estado',
        )
        self.company.invalidate_recordset(['name'])
        self.company.partner_id.invalidate_recordset(['name'])
        self.assertEqual(self.company.name, self.company_name)
        self.assertEqual(updated.name, 'Renier Ricardo Figueredo')
        self.assertNotEqual(updated, self.company.partner_id)

    def test_existing_device_on_company_partner_is_detached_on_reregister(self):
        company_partner = self.company.partner_id
        device = self.Device.create({
            'device_key': 'device-legacy-company-partner',
            'partner_id': company_partner.id,
            'company_id': self.company.id,
            'phone': self.shop_phone,
            'phone_validated': False,
            'active': True,
            'client_channel': 'apk',
        })
        result = self.Device.register_or_get(
            self.shop_phone,
            'device-legacy-company-partner',
            company=self.company,
        )
        device.invalidate_recordset(['partner_id'])
        self.assertFalse(result['created'])
        self.assertNotEqual(device.partner_id, company_partner)
        self.assertEqual(device.partner_id, result['partner'])
        self.assertEqual(self.company.name, self.company_name)

        municipality = self.Municipality.create({'name': 'Mun Legacy'})
        neighborhood = self.Neighborhood.create({
            'name': 'Bar Legacy',
            'municipality_id': municipality.id,
        })
        self.PartnerAddress.order_bridge_put_full(
            device.partner_id,
            'Renier Ricardo Figueredo',
            street='Calle Legacy',
            neighborhood_id=neighborhood.id,
            municipality_id=municipality.id,
            state='Estado',
        )
        self.company.invalidate_recordset(['name'])
        self.assertEqual(self.company.name, self.company_name)

    def test_profile_put_on_company_partner_detaches_before_rename(self):
        """Direct profile write against the company partner must not rename it."""
        company_partner = self.company.partner_id
        device = self.Device.create({
            'device_key': 'device-direct-company-profile',
            'partner_id': company_partner.id,
            'company_id': self.company.id,
            'phone': self.shop_phone,
            'phone_validated': False,
            'active': True,
            'client_channel': 'apk',
        })
        municipality = self.Municipality.create({'name': 'Mun Direct'})
        neighborhood = self.Neighborhood.create({
            'name': 'Bar Direct',
            'municipality_id': municipality.id,
        })
        updated = self.PartnerAddress.order_bridge_put_full(
            company_partner,
            'Renier Ricardo Figueredo',
            street='Calle Direct',
            neighborhood_id=neighborhood.id,
            municipality_id=municipality.id,
            state='Estado',
        )
        device.invalidate_recordset(['partner_id'])
        self.company.invalidate_recordset(['name'])
        self.assertEqual(self.company.name, self.company_name)
        self.assertEqual(company_partner.name, self.company_name)
        self.assertEqual(updated.name, 'Renier Ricardo Figueredo')
        self.assertEqual(device.partner_id, updated)
        self.assertNotEqual(updated, company_partner)
