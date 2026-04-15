# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class OrderBridgeBanner(models.Model):
    _name = 'order_bridge.banner'
    _description = 'Banner publicitario (Tienda Apk)'
    _order = 'sequence, id'

    title = fields.Char(required=True)
    subtitle = fields.Char()
    bg_color = fields.Char(string='Color de fondo')
    text_color = fields.Char(string='Color del texto')
    href = fields.Char(string='Enlace')
    image = fields.Image(string='Imagen')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        ondelete='cascade',
        default=lambda self: self.env.company,
        index=True,
    )

    def _can_return_content(self, field_name=None, access_token=None):
        """Allow public ``/web/image`` for banners activos del catálogo (misma compañía que la petición)."""
        if field_name != 'image':
            return super()._can_return_content(field_name, access_token)
        self.ensure_one()
        rec = self.sudo()
        if not rec.active or not rec.image:
            return False
        if rec.company_id != self.env.company:
            return False
        return True
