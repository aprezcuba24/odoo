# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Optional runtime patch for OCA fs.storage ``get_directory_path``.

OCA only substitutes ``{db_name}``. When ``ODOO_MULTI_COMPANY_S3`` is enabled,
``provision_media_fs_storage`` writes ``directory_path = <bucket>/{company_id}``.
This hook adds ``{company_id}`` substitution without adding ``fs.storage`` to
``depends`` (single-tenant without S3 is unchanged: no registry entry or path
without the placeholder → original OCA method).
"""

from __future__ import annotations

from odoo import models

COMPANY_ID_PLACEHOLDER = "{company_id}"


def patch_fs_storage_get_directory_path(registry) -> None:
    """Monkey-patch ``fs.storage.get_directory_path`` once per registry."""
    if "fs.storage" not in registry:
        return
    FsStorage = registry["fs.storage"]
    if getattr(FsStorage, "_order_bridge_company_id_path_patched", False):
        return

    original = FsStorage.get_directory_path

    def get_directory_path(self):
        path = self.directory_path
        if not isinstance(path, str) or COMPANY_ID_PLACEHOLDER not in path:
            return original(self)
        return path.format(
            db_name=self.env.cr.dbname,
            company_id=self.env.company.id,
        )

    FsStorage.get_directory_path = get_directory_path
    FsStorage._order_bridge_company_id_path_patched = True


class OrderBridgeFsStorageHook(models.AbstractModel):
    _name = "order_bridge.fs_storage.hook"
    _description = "Register fs.storage directory_path patch for multi-company S3"

    def _register_hook(self):
        super()._register_hook()
        patch_fs_storage_get_directory_path(self.pool)
