# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Tests for order_bridge S3 media fs.storage provisioning hooks."""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge import hooks as obhooks


@tagged("post_install", "-at_install")
class TestOrderBridgeS3Hooks(TransactionCase):
    def test_multi_tenant_enabled(self):
        with patch.dict("os.environ", {"ODOO_MULTI_TENANT": "true"}, clear=False):
            self.assertTrue(obhooks._multi_tenant_enabled())
        with patch.dict("os.environ", {"ODOO_MULTI_TENANT": "1"}, clear=False):
            self.assertTrue(obhooks._multi_tenant_enabled())
        with patch.dict("os.environ", {"ODOO_MULTI_TENANT": ""}, clear=False):
            self.assertFalse(obhooks._multi_tenant_enabled())
        with patch.dict("os.environ", {"ODOO_MULTI_TENANT": "false"}, clear=False):
            self.assertFalse(obhooks._multi_tenant_enabled())

    def test_directory_path_single_vs_multi_tenant(self):
        with patch.dict("os.environ", {"ODOO_MULTI_TENANT": ""}, clear=False):
            self.assertEqual(obhooks._media_directory_path("my-bucket"), "my-bucket")
        with patch.dict("os.environ", {"ODOO_MULTI_TENANT": "true"}, clear=False):
            self.assertEqual(
                obhooks._media_directory_path("my-bucket"),
                "my-bucket/{db_name}",
            )

    def test_discover_image_attachment_field_xmlids_includes_product(self):
        xmlids = obhooks._discover_image_attachment_field_xmlids(self.env)
        self.assertIn("product.field_product_template__image_1920", xmlids)
        self.assertTrue(
            any("image_variant_1920" in x for x in xmlids),
            f"expected product variant image field in {xmlids[:20]}...",
        )
        self.assertFalse(any(x.startswith("__export__") for x in xmlids))

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
            "ODOO_MULTI_TENANT": "true",
        }
        with patch.dict("os.environ", env_patch, clear=False):
            storage = obhooks.provision_media_fs_storage(self.env)

        self.assertTrue(storage)
        self.assertEqual(storage.code, obhooks.MEDIA_FS_STORAGE_CODE)
        self.assertEqual(storage.directory_path, "test-odoo-media-bucket/{db_name}")
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
