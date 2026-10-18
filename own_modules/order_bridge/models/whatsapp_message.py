# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OrderBridgeWhatsappMessage(models.Model):
    _name = 'order_bridge.whatsapp.message'
    _description = 'Mensaje genérico WhatsApp (Tienda Apk)'
    _order = 'position, sequence, id'

    name = fields.Char(required=True)
    position = fields.Selection(
        selection=[
            ('start', 'Al inicio'),
            ('end', 'Al final'),
        ],
        required=True,
        default='start',
        string='Posición',
    )
    body = fields.Text(string='Texto', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        ondelete='cascade',
        default=lambda self: self.env.company,
        index=True,
    )

    @api.constrains('body')
    def _check_message_content(self):
        for rec in self:
            if not (rec.body or '').strip():
                raise ValidationError(_('Un mensaje de texto debe tener cuerpo.'))

    @api.model
    def get_whatsapp_publisher_messages(self):
        """Active generic text messages for the current company, ready for the publisher UI.

        Returns rows ordered by position (start then end), then sequence.
        """
        messages = self.search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id),
        ])
        # Selection keys sort alphabetically (end before start); force start first.
        messages = messages.sorted(
            key=lambda m: (0 if m.position == 'start' else 1, m.sequence, m.id),
        )
        return [
            {
                'id': msg.id,
                'name': msg.name,
                'position': msg.position,
                'kind': 'text',
                'text': (msg.body or '').strip(),
            }
            for msg in messages
        ]
