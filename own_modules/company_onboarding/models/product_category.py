# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'company.onboarding.company.mixin']
