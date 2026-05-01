# SPDX-License-Identifier: LGPL-3.0-or-later

import base64
import logging
import os
import re
from collections import defaultdict

import boto3
from botocore.exceptions import ClientError

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


def _env_first(*keys: str) -> str:
    for key in keys:
        val = os.environ.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ''


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    @api.model
    def _attachment_s3_icp(self):
        return self.env['ir.config_parameter'].sudo()

    @api.model
    def _attachment_s3_merge_config(self, preview_settings=None):
        """Return dict with bucket, region, endpoint_url, access_key, secret_key, session_token, key_prefix
        or None if required fields are missing.
        """
        icp = self._attachment_s3_icp()

        def icp_val(key, default=''):
            return icp.get_param(key, default) or default

        bucket = _env_first('ODOO_S3_BUCKET', 'AWS_S3_BUCKET')
        if not bucket:
            bucket = (
                (preview_settings.attachment_s3_bucket or '').strip()
                if preview_settings
                else icp_val('attachment_s3.bucket')
            )

        region = _env_first('AWS_DEFAULT_REGION', 'AWS_REGION')
        if not region:
            region = (
                (preview_settings.attachment_s3_region or '').strip()
                if preview_settings
                else icp_val('attachment_s3.region')
            )

        endpoint = _env_first('AWS_ENDPOINT_URL')
        if not endpoint:
            endpoint = (
                (preview_settings.attachment_s3_endpoint_url or '').strip()
                if preview_settings
                else icp_val('attachment_s3.endpoint_url')
            )

        access_key = _env_first('AWS_ACCESS_KEY_ID')
        if not access_key:
            access_key = (
                (preview_settings.attachment_s3_access_key_id or '').strip()
                if preview_settings
                else icp_val('attachment_s3.access_key_id')
            )

        secret_key = _env_first('AWS_SECRET_ACCESS_KEY')
        if not secret_key:
            secret_key = (
                (preview_settings.attachment_s3_secret_access_key or '').strip()
                if preview_settings
                else icp_val('attachment_s3.secret_access_key')
            )

        session_token = _env_first('AWS_SESSION_TOKEN')

        prefix = _env_first('ODOO_S3_KEY_PREFIX')
        if not prefix:
            if preview_settings is not None:
                prefix = (preview_settings.attachment_s3_key_prefix or '').strip()
            else:
                prefix = icp_val('attachment_s3.key_prefix')
        if prefix:
            prefix = prefix.strip('/')
            if prefix:
                prefix = prefix + '/'

        if not bucket or not region or not access_key or not secret_key:
            return None
        return {
            'bucket': bucket,
            'region': region,
            'endpoint_url': endpoint or None,
            'access_key': access_key,
            'secret_key': secret_key,
            'session_token': session_token or None,
            'key_prefix': prefix,
        }

    @api.model
    def _attachment_s3_toggle_on(self, preview_settings=None):
        if preview_settings is not None:
            return bool(preview_settings.attachment_s3_enabled)
        return self._attachment_s3_icp().get_param('attachment_s3.enabled') == 'True'

    @api.model
    def _attachment_s3_runtime_enabled(self):
        """S3 I/O when enabled in settings and credentials are complete."""
        if not self._attachment_s3_toggle_on():
            return False
        return bool(self._attachment_s3_merge_config())

    @api.model
    def _attachment_s3_client(self, preview_settings=None):
        cfg = self._attachment_s3_merge_config(preview_settings=preview_settings)
        if not cfg:
            return None
        return boto3.client(
            's3',
            region_name=cfg['region'],
            endpoint_url=cfg['endpoint_url'],
            aws_access_key_id=cfg['access_key'],
            aws_secret_access_key=cfg['secret_key'],
            aws_session_token=cfg['session_token'],
        )

    @api.model
    def _attachment_s3_validate_config(self, preview_settings=None):
        if not self._attachment_s3_toggle_on(preview_settings=preview_settings):
            return
        cfg = self._attachment_s3_merge_config(preview_settings=preview_settings)
        if not cfg:
            raise UserError(
                _(
                    'S3 is enabled but configuration is incomplete. Set bucket, region, '
                    'access key and secret (in Settings or via environment variables).'
                )
            )
        client = self._attachment_s3_client(preview_settings=preview_settings)
        try:
            client.head_bucket(Bucket=cfg['bucket'])
        except ClientError as exc:
            code = exc.response.get('Error', {}).get('Code', '')
            _logger.warning('S3 head_bucket failed: %s', exc)
            raise UserError(
                _('Could not reach S3 bucket %(bucket)s: %(error)s')
                % {'bucket': cfg['bucket'], 'error': code or str(exc)}
            ) from exc

    @api.model
    def _attachment_s3_segment_slug(self, segment: str) -> str:
        slug = (segment or 'misc').lower()
        slug = re.sub(r'[^a-z0-9_-]+', '-', slug).strip('-') or 'misc'
        return slug[:80]

    @api.model
    def _attachment_s3_segment_for_values(self, values: dict) -> str:
        res_model = (values.get('res_model') or '').strip()
        if not res_model:
            return 'misc'
        return self._attachment_s3_segment_slug(res_model)

    @api.model
    def _attachment_s3_segment_for_record(self, attach):
        res_model = (attach.res_model or '').strip()
        if not res_model:
            return 'misc'
        return self._attachment_s3_segment_slug(res_model)

    @api.model
    def _attachment_s3_key_prefix_effective(self, preview_settings=None):
        cfg = self._attachment_s3_merge_config(preview_settings=preview_settings)
        if not cfg:
            return f'{self.env.cr.dbname}/'
        if cfg['key_prefix']:
            return cfg['key_prefix']
        return f'{self.env.cr.dbname}/'

    @api.model
    def _attachment_s3_is_layered_key(self, fname: str) -> bool:
        """Heuristic: our keys use at least segment/sha2/sha (two slashes after optional prefix)."""
        if not fname:
            return False
        return fname.count('/') >= 2

    # -------------------------------------------------------------------------
    # S3 primitives
    # -------------------------------------------------------------------------

    @api.model
    def _attachment_s3_bucket_key(self, fname: str):
        cfg = self._attachment_s3_merge_config()
        if not cfg:
            raise UserError(_('S3 is not configured.'))
        prefix = self._attachment_s3_key_prefix_effective()
        key = f'{prefix}{fname}'.lstrip('/')
        return cfg['bucket'], key

    @api.model
    def _attachment_s3_put(self, fname: str, data: bytes):
        client = self._attachment_s3_client()
        bucket, key = self._attachment_s3_bucket_key(fname)
        extra = {}
        if self.env.context.get('attachment_s3_content_type'):
            extra['ContentType'] = self.env.context['attachment_s3_content_type']
        client.put_object(Bucket=bucket, Key=key, Body=data, **extra)

    @api.model
    def _attachment_s3_get(self, fname: str, size=None) -> bytes:
        client = self._attachment_s3_client()
        bucket, key = self._attachment_s3_bucket_key(fname)
        params = {'Bucket': bucket, 'Key': key}
        if size:
            params['Range'] = f'bytes=0-{size - 1}'
        resp = client.get_object(**params)
        return resp['Body'].read()

    @api.model
    def _attachment_s3_delete_object(self, fname: str):
        client = self._attachment_s3_client()
        bucket, key = self._attachment_s3_bucket_key(fname)
        try:
            client.delete_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            _logger.info('S3 delete_object skipped/failed for %s: %s', key, exc)

    # -------------------------------------------------------------------------
    # Paths & I/O overrides
    # -------------------------------------------------------------------------

    @api.model
    def _get_path(self, bin_data, sha):
        if self._attachment_s3_runtime_enabled() and self._storage() != 'db':
            segment = self.env.context.get('attachment_s3_segment') or 'misc'
            segment = self._attachment_s3_segment_slug(segment)
            fname = f'{segment}/{sha[:2]}/{sha}'
            return fname, fname
        return super()._get_path(bin_data, sha)

    @api.model
    def _file_read(self, fname, size=None):
        if (
            self._attachment_s3_runtime_enabled()
            and self._storage() != 'db'
            and self._attachment_s3_is_layered_key(fname)
        ):
            try:
                return self._attachment_s3_get(fname, size=size)
            except ClientError as exc:
                code = exc.response.get('Error', {}).get('Code', '')
                if code in ('NoSuchKey', '404', 'NotFound'):
                    _logger.info('S3 miss for %s, trying filestore', fname)
                    return super()._file_read(fname, size=size)
                raise
        return super()._file_read(fname, size=size)

    @api.model
    def _file_write(self, bin_value, checksum):
        if self._attachment_s3_runtime_enabled() and self._storage() != 'db':
            attachments = self.env['ir.attachment'].sudo().search(
                [
                    ('checksum', '=', checksum),
                    ('store_fname', '!=', False),
                ]
            )
            fnames = list({a.store_fname for a in attachments if self._attachment_s3_is_layered_key(a.store_fname)})
            for fname in fnames:
                self._attachment_s3_put(fname, bin_value)
            if fnames:
                return fnames[0]
            fname, _full = self._get_path(bin_value, checksum)
            self._attachment_s3_put(fname, bin_value)
            return fname
        return super()._file_write(bin_value, checksum)

    @api.model
    def _file_delete(self, fname):
        if (
            self._attachment_s3_runtime_enabled()
            and self._storage() != 'db'
            and self._attachment_s3_is_layered_key(fname)
        ):
            self._attachment_s3_delete_object(fname)
            return
        return super()._file_delete(fname)

    def _mark_for_gc(self, fname):
        if self._attachment_s3_runtime_enabled() and self._storage() != 'db' and self._attachment_s3_is_layered_key(
            fname
        ):
            return
        return super()._mark_for_gc(fname)

    @api.autovacuum
    def _gc_file_store(self):
        if self._attachment_s3_runtime_enabled() and self._storage() != 'db':
            return False
        return super()._gc_file_store()

    def _set_attachment_data(self, asbytes):
        if not self._attachment_s3_runtime_enabled() or self._storage() == 'db':
            return super()._set_attachment_data(asbytes)

        old_fnames = []
        checksum_raw_map = {}
        for attach in self:
            bin_data = asbytes(attach)
            segment = self._attachment_s3_segment_for_record(attach)
            vals = attach.with_context(attachment_s3_segment=segment)._get_datas_related_values(
                bin_data, attach.mimetype
            )
            if bin_data:
                checksum_raw_map[vals['checksum']] = bin_data
            if attach.store_fname:
                old_fnames.append(attach.store_fname)
            super(IrAttachment, attach.sudo()).write(vals)

        if self._storage() != 'db':
            self.flush_recordset(['checksum', 'store_fname'])
            for fname in old_fnames:
                self._file_delete(fname)
            for checksum, raw in checksum_raw_map.items():
                self._file_write(raw, checksum)

    @api.model_create_multi
    def create(self, vals_list):
        if (
            self.env.context.get('attachment_s3_skip_create')
            or not self._attachment_s3_runtime_enabled()
            or self._storage() == 'db'
        ):
            return super().create(vals_list)

        record_tuple_set = set()
        vals_list = [
            {key: value for key, value in vals.items() if key not in ('file_size', 'checksum', 'store_fname')}
            for vals in vals_list
        ]
        checksum_raw_map = {}

        for values in vals_list:
            datas = values.pop('datas', None)
            if raw := values.get('raw'):
                if isinstance(raw, str):
                    values['raw'] = raw.encode()
            elif datas:
                values['raw'] = base64.b64decode(datas)
            else:
                values['raw'] = b''

            values = self._check_contents(values)
            if raw := values.pop('raw'):
                segment = self._attachment_s3_segment_for_values(values)
                vals_upd = self.with_context(attachment_s3_segment=segment)._get_datas_related_values(
                    raw, values['mimetype']
                )
                values.update(vals_upd)
                checksum_raw_map[vals_upd['checksum']] = raw

            record_tuple_set.add((values.get('res_model'), values.get('res_id')))

        model_and_ids = defaultdict(set)
        for res_model, res_id in record_tuple_set:
            model_and_ids[res_model].add(res_id)
        if any(self._inaccessible_comodel_records(model_and_ids, 'write')):
            raise AccessError(_('Sorry, you are not allowed to access this document.'))

        records = self.with_context(attachment_s3_skip_create=True).create(vals_list)
        for checksum, raw in checksum_raw_map.items():
            self._file_write(raw, checksum)
        records._check_serving_attachments()
        return records
