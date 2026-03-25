# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mobile_pos_config_id = fields.Many2one(
        'pos.config',
        string='Mobile app point of sale',
        related='company_id.mobile_pos_config_id',
        readonly=False,
        domain="[('company_id', '=', company_id)]",
        check_company=True,
        help='Only products available in this point of sale are shown in the mobile app.',
    )
