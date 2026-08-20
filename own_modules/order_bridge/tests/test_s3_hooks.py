# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Tests for order_bridge S3 media fs.storage provisioning hooks."""

from unittest.mock import patch

from odoo import fields as odoo_fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge import hooks as obhooks
from odoo.addons.order_bridge.models.fs_storage_hook import (
    COMPANY_ID_PLACEHOLDER,
    patch_fs_storage_get_directory_path,
)


@tagged("post_install", "-at_install")
class TestOrderBridgeS3Hooks(TransactionCase):
    def test_directory_path_single_vs_multi_company(self):
        with patch.dict(
            "os.environ",
            {"ODOO_MULTI_COMPANY_S3": ""},
            clear=False,
        ):
            self.assertEqual(obhooks._media_directory_path("my-bucket"), "my-bucket")
        with patch.dict(
            "os.environ",
            {"ODOO_MULTI_COMPANY_S3": "true"},
            clear=False,
        ):
            self.assertEqual(
                obhooks._media_directory_path("my-bucket"),
                "my-bucket/{company_id}",
            )

    def test_discover_image_attachment_field_xmlids_includes_product(self):
        xmlids = obhooks._discover_image_attachment_field_xmlids(self.env)
        self.assertIn("product.field_product_template__image_1920", xmlids)
        self.assertTrue(
            any("image_variant_1920" in x for x in xmlids),
            f"expected product variant image field in {xmlids[:20]}...",
        )
        self.assertFalse(any(x.startswith("__export__") for x in xmlids))

    def test_discover_user_media_excludes_edi_attachment_binaries(self):
        xmlids = obhooks._discover_image_attachment_field_xmlids(self.env)
        self.assertFalse(
            any("edi_attachment" in x or "attachment_file" in x for x in xmlids),
            "EDI/PDF attachment binaries must not be routed to S3",
        )

    def test_is_user_media_attachment_field_by_name_and_type(self):
        product_field = self.env["product.template"]._fields["image_1920"]
        self.assertTrue(obhooks._is_user_media_attachment_field(product_field))
        logo_like = type(
            "LogoField",
            (odoo_fields.Binary,),
            {"name": "company_logo", "attachment": True},
        )()
        self.assertTrue(obhooks._is_user_media_attachment_field(logo_like))
        edi_like = type(
            "EdiField",
            (odoo_fields.Binary,),
            {"name": "l10n_edi_attachment_file", "attachment": True},
        )()
        self.assertFalse(obhooks._is_user_media_attachment_field(edi_like))

    def test_provision_media_fs_storage_sets_model_and_field_xmlids(self):
        fs_mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "fs_attachment")], limit=1
        )
        if not fs_mod or fs_mod.state != "installed":
            self.skipTest("fs_attachment not installed")

        env_patch = {
            "ORDER_BRIDGE_BANNER_S3_BUCKET": "test-odoo-media-bucket",
            "AWS_ACCESS_KEY_ID": "AKIA_TEST",
            "AWS_SECRET_ACCESS_KEY": "secret_test",
            "AWS_DEFAULT_REGION": "us-east-1",
            "ODOO_MULTI_COMPANY_S3": "",
        }
        with patch.dict("os.environ", env_patch, clear=False):
            storage = obhooks.provision_media_fs_storage(self.env)

        self.assertTrue(storage)
        self.assertEqual(storage.code, obhooks.MEDIA_FS_STORAGE_CODE)
        self.assertEqual(storage.directory_path, "test-odoo-media-bucket")
        self.assertEqual(storage.model_xmlids, obhooks.BANNER_MODEL_XMLID)
        self.assertFalse(storage.use_as_default_for_attachments)
        self.assertIn(
            "product.field_product_template__image_1920",
            (storage.field_xmlids or "").split(","),
        )

    def test_provision_banner_fs_storage_alias(self):
        self.assertIs(
            obhooks.provision_banner_fs_storage,
            obhooks.provision_media_fs_storage,
        )

    def test_get_directory_path_single_tenant_unchanged(self):
        fs_mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "fs_storage")], limit=1
        )
        if not fs_mod or fs_mod.state != "installed":
            self.skipTest("fs_storage not installed")

        Storage = self.env["fs.storage"].sudo()
        storage = Storage.create(
            {
                "name": "ST test storage",
                "code": "test_order_bridge_st_path",
                "protocol": "file",
                "directory_path": "my-bucket",
            }
        )
        patch_fs_storage_get_directory_path(self.registry)
        self.assertEqual(storage.get_directory_path(), "my-bucket")
        storage.unlink()

    def test_get_directory_path_multi_company_resolves_company_id(self):
        fs_mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "fs_storage")], limit=1
        )
        if not fs_mod or fs_mod.state != "installed":
            self.skipTest("fs_storage not installed")

        Storage = self.env["fs.storage"].sudo()
        storage = Storage.create(
            {
                "name": "MC test storage",
                "code": "test_order_bridge_mc_path",
                "protocol": "file",
                "directory_path": f"my-bucket/{COMPANY_ID_PLACEHOLDER}",
            }
        )
        patch_fs_storage_get_directory_path(self.registry)
        company_id = self.env.company.id
        self.assertEqual(
            storage.get_directory_path(),
            f"my-bucket/{company_id}",
        )
        storage.unlink()
