# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosCategory(models.Model):
    _name = 'pos.category'
    _inherit = ['pos.category', 'company.onboarding.company.mixin']
