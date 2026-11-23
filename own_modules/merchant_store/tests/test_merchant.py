# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge import hooks as obhooks


@tagged('post_install', '-at_install')
class TestMerchantStoreMerchant(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_a = Company.create({
            'name': 'Merchant Co A',
            'order_bridge_slug': 'merchant-co-a',
        })
        cls.company_b = Company.create({
            'name': 'Merchant Co B',
            'order_bridge_slug': 'merchant-co-b',
        })
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        group_user = cls.env.ref('merchant_store.group_merchant_store_user')
        group_base = cls.env.ref('base.group_user')
        cls.user_a = Users.create({
            'name': 'Merchant User A',
            'login': 'merchant_user_a',
            'password': 'merchant_user_a',
            'company_id': cls.company_a.id,
            'company_ids': [Command.set([cls.company_a.id])],
            'group_ids': [Command.set([group_base.id, group_user.id])],
        })
        cls.user_b = Users.create({
            'name': 'Merchant User B',
            'login': 'merchant_user_b',
            'password': 'merchant_user_b',
            'company_id': cls.company_b.id,
            'company_ids': [Command.set([cls.company_b.id])],
            'group_ids': [Command.set([group_base.id, group_user.id])],
        })
        cls.user_no_group = Users.create({
            'name': 'Merchant No Group',
            'login': 'merchant_no_group',
            'password': 'merchant_no_group',
            'company_id': cls.company_a.id,
            'company_ids': [Command.set([cls.company_a.id])],
            'group_ids': [Command.set([group_base.id])],
        })

    def test_create_merchant_fields_and_default_company(self):
        Merchant = self.env['merchant_store.merchant'].with_company(self.company_a)
        merchant = Merchant.create({
            'name': 'Comerciante Demo',
            'description': 'Descripción de prueba',
        })
        self.assertEqual(merchant.name, 'Comerciante Demo')
        self.assertEqual(merchant.description, 'Descripción de prueba')
        self.assertFalse(merchant.logo)
        self.assertTrue(merchant.active)
        self.assertEqual(merchant.company_id, self.company_a)

    def test_company_isolation_search_and_browse(self):
        Merchant = self.env['merchant_store.merchant']
        merchant_a = Merchant.create({
            'name': 'Merchant A',
            'company_id': self.company_a.id,
        })
        merchant_b = Merchant.create({
            'name': 'Merchant B',
            'company_id': self.company_b.id,
        })

        found_a = Merchant.with_user(self.user_a).with_company(self.company_a).search([])
        found_b = Merchant.with_user(self.user_b).with_company(self.company_b).search([])
        self.assertEqual(found_a, merchant_a)
        self.assertEqual(found_b, merchant_b)

        with self.assertRaises(AccessError):
            merchant_b.with_user(self.user_a).with_company(self.company_a).read(['name'])

    def test_user_without_group_cannot_read(self):
        merchant = self.env['merchant_store.merchant'].create({
            'name': 'Hidden Merchant',
            'company_id': self.company_a.id,
        })
        with self.assertRaises(AccessError):
            merchant.with_user(self.user_no_group).read(['name'])

    def test_logo_field_discovered_for_s3(self):
        logo_xmlid = 'merchant_store.field_merchant_store_merchant__logo'
        xmlids = obhooks._discover_image_attachment_field_xmlids(self.env)
        self.assertIn(logo_xmlid, xmlids)

        fs_mod = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'fs_attachment')], limit=1
        )
        if not fs_mod or fs_mod.state != 'installed':
            self.skipTest('fs_attachment not installed')

        Storage = self.env['fs.storage'].sudo()
        env_patch = {
            'ORDER_BRIDGE_BANNER_S3_BUCKET': 'test-merchant-media-bucket',
            'AWS_ACCESS_KEY_ID': 'AKIA_TEST',
            'AWS_SECRET_ACCESS_KEY': 'secret_test',
            'AWS_DEFAULT_REGION': 'us-east-1',
            'ODOO_MULTI_COMPANY_S3': '',
        }
        with patch.dict('os.environ', env_patch, clear=False):
            canonical = Storage.search(
                [('code', '=', obhooks.MEDIA_FS_STORAGE_CODE)], limit=1
            )
            if canonical:
                storage = obhooks.provision_media_fs_storage(self.env)
            else:
                # model_xmlids is server-env (not SQL-searchable). Local DBs may
                # already route the banner model through another fs.storage code.
                conflict = Storage.search([]).filtered(
                    lambda s: obhooks.BANNER_MODEL_XMLID
                    in (s.model_xmlids or '').split(',')
                )[:1]
                if conflict:
                    conflict.write({
                        'field_xmlids': ','.join(xmlids) if xmlids else False,
                    })
                    storage = conflict
                else:
                    storage = obhooks.provision_media_fs_storage(self.env)

        self.assertTrue(storage)
        field_xmlids = (storage.field_xmlids or '').split(',')
        self.assertIn(logo_xmlid, field_xmlids)
        self.assertIn('product.field_product_template__image_1920', field_xmlids)
