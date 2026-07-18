# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Optional provisioning of OCA fs_attachment + fs.storage (S3) for Tienda Apk media.

Requires ``fs_attachment`` installed. When environment variables for the bucket
and credentials are set, creates or updates ``fs.storage`` code
``s3_order_bridge_banners`` with:

- ``model_xmlids`` for ``order_bridge.banner`` (OCA resolves storage via
  ``model_xmlids`` / ``field_xmlids``, not ``ir.model.storage_id``)
- ``field_xmlids`` auto-discovered per database: stored binary fields whose
  name contains ``image`` and whose registry field has ``attachment=True``
  (Odoo 19: ``attachment`` is not a searchable column on ``ir.model.fields``)

Bucket name (first match wins):

- ``ORDER_BRIDGE_BANNER_S3_BUCKET`` (preferred)
- ``ODOO_S3_BUCKET`` (fallback)

S3 layout:

- **Single-tenant** (production; ``ODOO_MULTI_TENANT`` unset):
  ``directory_path = <bucket>`` — objects at bucket root.
- **Multi-tenant** (``ODOO_MULTI_TENANT=true``):
  ``directory_path = <bucket>/{db_name}`` — shared bucket, one prefix per
  database (OCA substitutes ``{db_name}`` at runtime).

``use_as_default_for_attachments`` stays False so regenerable assets
(JS/CSS) stay in DB/filestore.

Existing images uploaded before this setup stay in the database or
filestore until re-saved (or migrated with a custom script).
"""

from __future__ import annotations

import json
import logging
import os

_logger = logging.getLogger(__name__)

MEDIA_FS_STORAGE_CODE = "s3_order_bridge_banners"
# Backward-compatible alias for scripts / docs that still use the old name.
BANNER_FS_STORAGE_CODE = MEDIA_FS_STORAGE_CODE

BANNER_MODEL_XMLID = "order_bridge.model_order_bridge_banner"


def _multi_tenant_enabled() -> bool:
    return os.environ.get("ODOO_MULTI_TENANT", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _media_s3_bucket() -> str:
    """Preferred ``ORDER_BRIDGE_BANNER_S3_BUCKET``, else ``ODOO_S3_BUCKET``."""
    return (
        os.environ.get("ORDER_BRIDGE_BANNER_S3_BUCKET")
        or os.environ.get("ODOO_S3_BUCKET")
        or ""
    ).strip()


# Backward-compatible alias.
_banner_s3_bucket = _media_s3_bucket


def _media_directory_path(bucket: str) -> str:
    """Bucket root in single-tenant; ``bucket/{db_name}`` when multi-tenant."""
    if _multi_tenant_enabled():
        return f"{bucket}/{{db_name}}"
    return bucket


# Backward-compatible alias.
_banner_directory_path = _media_directory_path


def _s3_credentials() -> tuple[str, str]:
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
    return access_key, secret_key


def _s3_options(access_key: str, secret_key: str) -> dict:
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
    return options


def _discover_image_attachment_field_xmlids(env) -> list[str]:
    """Return XML IDs of stored binary fields whose name looks like an image.

    In Odoo 19 ``ir.model.fields`` has no searchable ``attachment`` column; the
    Binary/Image ``attachment`` flag lives on the registry field. We search
    stored binary fields with ``image`` in the name, then keep those whose
    registry field has ``attachment=True``. Excludes ``__export__`` XML IDs.
    """
    Field = env["ir.model.fields"].sudo()
    candidates = Field.search(
        [
            ("ttype", "=", "binary"),
            ("store", "=", True),
            ("model_id.transient", "=", False),
            ("name", "ilike", "image"),
        ]
    )
    keep = Field.browse()
    for irec in candidates:
        model_name = irec.model
        if model_name not in env:
            continue
        model_field = env[model_name]._fields.get(irec.name)
        if model_field is not None and getattr(model_field, "attachment", False):
            keep |= irec
    xmlids_map = keep.get_external_id()
    return sorted(
        x
        for x in xmlids_map.values()
        if x and not x.startswith("__export__")
    )


def provision_media_fs_storage(env):
    """Create/update S3 fs.storage for banners + image fields (idempotent)."""
    mod = env["ir.module.module"].sudo().search([("name", "=", "fs_attachment")], limit=1)
    if not mod or mod.state != "installed":
        _logger.info(
            "order_bridge: fs_attachment not installed; skip S3 media storage provisioning"
        )
        return

    banner_model = (
        env["ir.model"].sudo().search([("model", "=", "order_bridge.banner")], limit=1)
    )
    if not banner_model:
        _logger.info(
            "order_bridge: model order_bridge.banner not loaded; "
            "skip S3 media storage provisioning"
        )
        return

    bucket = _media_s3_bucket()
    if not bucket:
        return

    access_key, secret_key = _s3_credentials()
    if not access_key or not secret_key:
        _logger.warning(
            "order_bridge: S3 bucket set (%s) but access key/secret "
            "missing (ORDER_BRIDGE_* or AWS_*); skip fs.storage provisioning",
            bucket,
        )
        return

    field_xmlids = _discover_image_attachment_field_xmlids(env)
    directory_path = _media_directory_path(bucket)
    multi_tenant = _multi_tenant_enabled()
    options = _s3_options(access_key, secret_key)

    Storage = env["fs.storage"].sudo()
    vals = {
        "name": "Tienda Apk media (S3)",
        "code": MEDIA_FS_STORAGE_CODE,
        "protocol": "s3",
        "directory_path": directory_path,
        "eval_options_from_env": False,
        "options": json.dumps(options),
        "optimizes_directory_path": True,
        "autovacuum_gc": True,
        "use_as_default_for_attachments": False,
        # OCA resolves via model_xmlids / field_xmlids (not ir.model.storage_id).
        "model_xmlids": BANNER_MODEL_XMLID,
        "field_xmlids": ",".join(field_xmlids) if field_xmlids else False,
    }

    existing = Storage.search([("code", "=", MEDIA_FS_STORAGE_CODE)], limit=1)
    if existing:
        existing.write(vals)
        storage = existing
    else:
        storage = Storage.create(vals)

    _logger.info(
        "order_bridge: fs.storage %s directory_path=%s multi_tenant=%s "
        "model_xmlids=%s field_xmlids_count=%s",
        MEDIA_FS_STORAGE_CODE,
        directory_path,
        multi_tenant,
        BANNER_MODEL_XMLID,
        len(field_xmlids),
    )
    if field_xmlids:
        _logger.info(
            "order_bridge: S3 image field_xmlids sample=%s%s",
            ",".join(field_xmlids[:5]),
            "..." if len(field_xmlids) > 5 else "",
        )
    else:
        _logger.warning(
            "order_bridge: no image attachment fields discovered for fs.storage %s",
            MEDIA_FS_STORAGE_CODE,
        )

    return storage


# Backward-compatible alias used by docker-entrypoint / provision_tenant.sh.
provision_banner_fs_storage = provision_media_fs_storage


def post_init_hook(env):
    """Odoo 19 passes ``env`` to ``post_init_hook`` (see odoo/modules/loading.py)."""
    provision_media_fs_storage(env)
