# SPDX-License-Identifier: LGPL-3.0-or-later

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attachment_s3_enabled = fields.Boolean(
        string='Use S3 for file attachments',
        config_parameter='attachment_s3.enabled',
        help='Requires ir_attachment.location=file. When enabled, binary attachments use the '
        'configured bucket. Prefer AWS_* / ODOO_S3_BUCKET in environment (see module README).',
    )
    attachment_s3_bucket = fields.Char(
        string='S3 bucket',
        config_parameter='attachment_s3.bucket',
        help='Overridden by ODOO_S3_BUCKET or AWS_S3_BUCKET if set.',
    )
    attachment_s3_region = fields.Char(
        string='AWS region',
        config_parameter='attachment_s3.region',
        help='Overridden by AWS_DEFAULT_REGION or AWS_REGION if set.',
    )
    attachment_s3_endpoint_url = fields.Char(
        string='Endpoint URL (optional)',
        config_parameter='attachment_s3.endpoint_url',
        help='Leave empty for AWS. Overridden by AWS_ENDPOINT_URL.',
    )
    attachment_s3_key_prefix = fields.Char(
        string='Key prefix',
        config_parameter='attachment_s3.key_prefix',
        help='Optional. Default: database name + slash.',
    )
    attachment_s3_access_key_id = fields.Char(
        string='AWS access key ID',
        config_parameter='attachment_s3.access_key_id',
        help='Overridden by AWS_ACCESS_KEY_ID if set.',
    )
    attachment_s3_secret_access_key = fields.Char(
        string='AWS secret access key',
        config_parameter='attachment_s3.secret_access_key',
        help='Overridden by AWS_SECRET_ACCESS_KEY if set.',
    )

    def set_values(self):
        if self.attachment_s3_enabled:
            self.env['ir.attachment'].sudo()._attachment_s3_validate_config(preview_settings=self)
        return super().set_values()
