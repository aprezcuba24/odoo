# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.order_bridge.utils.constant import (
    DELIVERY_NOTE_MAX_LENGTH,
    STATE_CANCELED,
)

AUTHOR_ADMIN = 'admin'
AUTHOR_MESSENGER = 'messenger'


class OrderBridgeDeliveryNote(models.Model):
    _name = 'order_bridge.delivery.note'
    _description = 'Nota de entrega (mensajero / administrador)'
    _order = 'create_date asc, id asc'

    order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
        required=True,
        ondelete='cascade',
        index=True,
    )
    author = fields.Selection(
        selection=[
            (AUTHOR_ADMIN, 'Administrador'),
            (AUTHOR_MESSENGER, 'Mensajero'),
        ],
        string='Autor',
        required=True,
        default=AUTHOR_ADMIN,
        index=True,
    )
    body = fields.Text(string='Nota', required=True)
    messenger_id = fields.Many2one(
        'order_bridge.messenger',
        string='Mensajero',
        ondelete='set null',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        ondelete='set null',
        default=lambda self: self.env.user,
    )
    reviewed = fields.Boolean(
        string='Revisada',
        default=True,
        help='Las notas del mensajero empiezan sin revisar; las del administrador ya están revisadas.',
    )

    @api.constrains('body')
    def _check_body(self):
        for note in self:
            text = (note.body or '').strip()
            if not text:
                raise ValidationError(_('La nota de entrega no puede estar vacía.'))
            if len(text) > DELIVERY_NOTE_MAX_LENGTH:
                raise ValidationError(
                    _(
                        'La nota de entrega no puede superar %(max)s caracteres.',
                        max=DELIVERY_NOTE_MAX_LENGTH,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            author = vals.get('author') or AUTHOR_ADMIN
            vals['author'] = author
            body = vals.get('body')
            if isinstance(body, str):
                vals['body'] = body.strip()
            if author == AUTHOR_ADMIN:
                vals.setdefault('user_id', self.env.uid)
                vals['reviewed'] = True
                vals['messenger_id'] = False
            elif author == AUTHOR_MESSENGER:
                vals['reviewed'] = False
                vals.setdefault('user_id', False)
            order = self.env['sale.order'].browse(vals.get('order_id')).exists()
            if order and order.order_bridge_store_state == STATE_CANCELED:
                raise UserError(
                    _('No se pueden añadir notas de entrega a un pedido cancelado.')
                )
        notes = super().create(vals_list)
        for note in notes.filtered(lambda n: n.author == AUTHOR_MESSENGER):
            note.order_id._order_bridge_on_messenger_note(note)
        return notes

    def write(self, vals):
        if 'body' in vals and isinstance(vals['body'], str):
            vals = {**vals, 'body': vals['body'].strip()}
        if 'author' in vals:
            raise UserError(_('No se puede cambiar el autor de una nota de entrega.'))
        return super().write(vals)
