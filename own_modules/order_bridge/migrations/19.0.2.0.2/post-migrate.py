# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Remove UI records dropped from the module (company/settings POS fields)."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in (
        'order_bridge.view_company_form_order_bridge',
        'order_bridge.res_config_settings_view_form_order_bridge',
    ):
        try:
            vid = env['ir.model.data']._xmlid_to_res_id(xmlid)
        except ValueError:
            continue
        env['ir.ui.view'].browse(vid).unlink()
