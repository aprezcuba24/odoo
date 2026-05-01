# SPDX-License-Identifier: LGPL-3.0-or-later
{
    'name': 'Attachment S3 storage',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Store ir.attachment file binaries in Amazon S3 or S3-compatible object storage',
    'description': (
        'Optional S3-backed storage for Odoo file attachments when enabled in Settings. '
        'Supports environment variables and UI configuration (env wins). '
        'See README.md for AWS bucket setup and IAM.'
    ),
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
