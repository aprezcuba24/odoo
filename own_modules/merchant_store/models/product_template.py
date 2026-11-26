# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    merchant_id = fields.Many2one(
        'merchant_store.merchant',
        string='Comerciante',
        ondelete='restrict',
        index=True,
        check_company=True,
    )

    @api.onchange('merchant_id')
    def _onchange_merchant_id_company(self):
        """Set the product company from the merchant chosen in the form."""
        if self.merchant_id:
            self.company_id = self.merchant_id.company_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._merchant_store_apply_isolation_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._merchant_store_apply_isolation_vals(vals, records=self)
        return super().write(vals)

    @api.model
    def _merchant_store_apply_isolation_vals(self, vals, records=None):
        """Force company and store flags when the product belongs to a merchant."""
        if 'merchant_id' in vals:
            merchant_id = vals.get('merchant_id')
            if merchant_id:
                merchant = self.env['merchant_store.merchant'].browse(merchant_id)
                vals['company_id'] = merchant.company_id.id
                vals['order_bridge_visible'] = False
                vals['available_in_pos'] = False
            return

        if records is None or not records:
            return

        merchant_products = records.filtered('merchant_id')
        if not merchant_products or merchant_products != records:
            return

        vals['order_bridge_visible'] = False
        vals['available_in_pos'] = False
        companies = merchant_products.mapped('merchant_id.company_id')
        if len(companies) == 1:
            vals['company_id'] = companies.id
