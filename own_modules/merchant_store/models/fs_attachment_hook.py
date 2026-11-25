# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Optional runtime patch for OCA fs_attachment ``ir.attachment._get_fs_path``.

Places merchant logos and merchant product images in per-merchant subfolders
inside the shared S3 media storage (``s3_order_bridge_banners``):

- Merchant logo: ``merchants/{merchant_id}/logo/<oca_hash_path>``
- Merchant product image (template or variant):
  ``merchants/{merchant_id}/products/{product_tmpl_id}/<oca_hash_path>``

Standard Tienda Apk products (``merchant_id`` empty) and banners keep the
default OCA path unchanged. When ``fs_attachment`` is not installed, this hook
does nothing.
"""

from __future__ import annotations

from odoo import models


def _merchant_fs_subdir(env, res_model, res_field, res_id) -> str | None:
    """Return S3 subfolder prefix for merchant logos and merchant product images."""
    if not res_model or not res_field or not res_id:
        return None
    if res_model == 'merchant_store.merchant' and res_field.startswith('logo'):
        return f'merchants/{res_id}/logo'
    if res_model == 'product.template' and res_field.startswith('image'):
        tmpl = env['product.template'].sudo().browse(res_id).exists()
        if tmpl and tmpl.merchant_id:
            return f'merchants/{tmpl.merchant_id.id}/products/{tmpl.id}'
    if res_model == 'product.product' and res_field.startswith('image'):
        product = env['product.product'].sudo().browse(res_id).exists()
        tmpl = product.product_tmpl_id if product else None
        if tmpl and tmpl.merchant_id:
            return f'merchants/{tmpl.merchant_id.id}/products/{tmpl.id}'
    return None


def patch_ir_attachment_get_fs_path(registry) -> None:
    """Monkey-patch ``ir.attachment._get_fs_path`` once per registry."""
    if 'fs.storage' not in registry or 'ir.attachment' not in registry:
        return
    IrAttachment = registry['ir.attachment']
    if not hasattr(IrAttachment, '_get_fs_path'):
        return
    if getattr(IrAttachment, '_merchant_store_fs_path_patched', False):
        return

    original = IrAttachment._get_fs_path

    def _get_fs_path(self, storage_code: str, bin_data: bytes) -> str:
        key = original(self, storage_code, bin_data)
        if self.env.context.get('force_storage_key'):
            return key
        subdir = _merchant_fs_subdir(
            self.env,
            self.env.context.get('attachment_res_model'),
            self.env.context.get('attachment_res_field'),
            self.env.context.get('attachment_res_id'),
        )
        if subdir:
            return f'{subdir}/{key}'
        return key

    IrAttachment._get_fs_path = _get_fs_path
    IrAttachment._merchant_store_fs_path_patched = True


class MerchantStoreFsAttachmentHook(models.AbstractModel):
    _name = 'merchant_store.fs_attachment.hook'
    _description = 'Register ir.attachment _get_fs_path patch for merchant S3 subfolders'

    def _register_hook(self):
        super()._register_hook()
        patch_ir_attachment_get_fs_path(self.pool)
