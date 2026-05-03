# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Optional provisioning of OCA fs_attachment + fs.storage (S3) for banner images.

Requires ``fs_attachment`` installed. When environment variables for the bucket
and credentials are set, creates or updates ``fs.storage`` code
``s3_order_bridge_banners`` and assigns ``ir.model.storage_id`` for
``order_bridge.banner``.

Existing banner images uploaded before this setup stay in the database or
filestore until re-saved (or migrated with a custom script).
"""

from __future__ import annotations

import json
import logging
import os

_logger = logging.getLogger(__name__)

BANNER_FS_STORAGE_CODE = "s3_order_bridge_banners"


def provision_banner_fs_storage(env):
    """Create/update S3 fs.storage and bind ``order_bridge.banner`` (idempotent)."""
    mod = env["ir.module.module"].sudo().search([("name", "=", "fs_attachment")], limit=1)
    if not mod or mod.state != "installed":
        _logger.info(
            "order_bridge: fs_attachment not installed; skip S3 banner storage provisioning"
        )
        return

    imodel = env["ir.model"].sudo().search([("model", "=", "order_bridge.banner")], limit=1)
    if not imodel:
        _logger.info(
            "order_bridge: model order_bridge.banner not loaded; skip S3 banner storage provisioning"
        )
        return

    bucket = (os.environ.get("ORDER_BRIDGE_BANNER_S3_BUCKET") or "").strip()
    if not bucket:
        return

    access_key = (
        os.environ.get("ORDER_BRIDGE_BANNER_S3_ACCESS_KEY_ID")
        or os.environ.get("AWS_ACCESS_KEY_ID")
        or ""
    ).strip()
    secret_key = (
        os.environ.get("ORDER_BRIDGE_BANNER_S3_SECRET_ACCESS_KEY")
        or os.environ.get("AWS_SECRET_ACCESS_KEY")
        or ""
    ).strip()
    if not access_key or not secret_key:
        _logger.warning(
            "order_bridge: ORDER_BRIDGE_BANNER_S3_BUCKET set but access key/secret "
            "missing (ORDER_BRIDGE_* or AWS_*); skip fs.storage provisioning"
        )
        return

    options: dict = {"key": access_key, "secret": secret_key}
    endpoint = (
        os.environ.get("ORDER_BRIDGE_BANNER_S3_ENDPOINT_URL")
        or os.environ.get("AWS_ENDPOINT_URL")
        or ""
    ).strip()
    region = (
        os.environ.get("ORDER_BRIDGE_BANNER_S3_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or ""
    ).strip()
    client_kwargs: dict = {}
    if region:
        client_kwargs["region_name"] = region
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint
    if client_kwargs:
        options["client_kwargs"] = client_kwargs

    Storage = env["fs.storage"].sudo()
    vals = {
        "name": "Tienda Apk banners (S3)",
        "code": BANNER_FS_STORAGE_CODE,
        "protocol": "s3",
        "directory_path": bucket,
        "eval_options_from_env": False,
        "options": json.dumps(options),
        "optimizes_directory_path": True,
        "autovacuum_gc": True,
        "use_as_default_for_attachments": False,
    }

    existing = Storage.search([("code", "=", BANNER_FS_STORAGE_CODE)], limit=1)
    if existing:
        existing.write(vals)
        storage = existing
    else:
        storage = Storage.create(vals)

    if imodel.storage_id != storage:
        imodel.write({"storage_id": storage.id})
        _logger.info(
            "order_bridge: linked model order_bridge.banner to fs.storage %s",
            BANNER_FS_STORAGE_CODE,
        )
    elif imodel:
        _logger.info(
            "order_bridge: model order_bridge.banner already uses fs.storage %s",
            BANNER_FS_STORAGE_CODE,
        )


def post_init_hook(env):
    """Odoo 19 passes ``env`` to ``post_init_hook`` (see odoo/modules/loading.py)."""
    provision_banner_fs_storage(env)
