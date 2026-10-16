# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


def _user_can_manage_category(user):
    """Return True if *user* may create/rename/re-parent/delete product categories.

    Allowed groups: Responsible Tienda Apk, Responsible de producto (Inventario),
    and superusers.
    """
    if user._is_superuser():
        return True
    if user.has_group('order_bridge.group_order_bridge_manager'):
        return True
    if user.has_group('product.group_product_manager'):
        return True
    return False


class ProductCategory(models.Model):
    _inherit = 'product.category'

    order_bridge_sequence = fields.Integer(
        string='Orden en la app',
        default=10,
        index=True,
        help='Orden en el que esta categoría aparece en Tienda Apk. '
             'A menor número, antes. A igual número se usa el orden alfabético.',
    )

    # Non-stored helper so views can show/hide editable name & parent_id
    order_bridge_can_manage = fields.Boolean(
        string='Puede gestionar categoría',
        compute='_compute_order_bridge_can_manage',
    )

    @api.depends_context('uid')
    def _compute_order_bridge_can_manage(self):
        can = _user_can_manage_category(self.env.user)
        for rec in self:
            rec.order_bridge_can_manage = can

    # ------------------------------------------------------------------
    # Access control overrides
    # ------------------------------------------------------------------

    def write(self, vals):
        """Vendedores solo pueden cambiar el campo de orden."""
        if not _user_can_manage_category(self.env.user):
            restricted = set(vals.keys()) - {'order_bridge_sequence'}
            if restricted:
                raise AccessError(
                    _(
                        'Solo los responsables de Tienda Apk o de Producto pueden '
                        'modificar los campos: %s.',
                        ', '.join(sorted(restricted)),
                    )
                )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if not _user_can_manage_category(self.env.user):
            raise AccessError(
                _(
                    'Solo los responsables de Tienda Apk o de Producto pueden '
                    'crear categorías de producto.'
                )
            )
        return super().create(vals_list)

    def unlink(self):
        if not _user_can_manage_category(self.env.user):
            raise AccessError(
                _(
                    'Solo los responsables de Tienda Apk o de Producto pueden '
                    'eliminar categorías de producto.'
                )
            )
        return super().unlink()
