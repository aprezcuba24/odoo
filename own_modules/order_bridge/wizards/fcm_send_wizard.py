# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.order_bridge.utils.constant import FCM_TOPIC_ALL_USERS
from odoo.addons.order_bridge.utils.fcm_topic import validate_fcm_topic_string


def validate_app_route(route: str) -> str:
    """Sanity-check de ruta relativa (sin catálogo de pantallas de la app).

    Exige barra inicial y rechaza esquemas, ``//``, ``..`` y espacios.
    Qué rutas navegan de verdad lo decide la APK; una ruta desconocida
    solo trae la app al frente.
    """
    route = (route or '').strip()
    if not route:
        raise ValueError('empty')
    if (
        not route.startswith('/')
        or ' ' in route
        or '//' in route
        or '..' in route
        or ':' in route
    ):
        raise ValueError(route)
    return route


class OrderBridgeFcmSendWizard(models.TransientModel):
    _name = 'order_bridge.fcm.send.wizard'
    _description = 'Enviar notificación push FCM'

    target_mode = fields.Selection(
        [
            ('single_partner', 'Un contacto'),
            ('multi_partner', 'Varios contactos'),
            ('topic', 'Topic FCM (campaña)'),
        ],
        string='Destino',
        required=True,
        default='single_partner',
    )
    partner_id = fields.Many2one('res.partner', string='Contacto')
    partner_ids = fields.Many2many('res.partner', string='Contactos')
    fcm_topic = fields.Char(
        string='Topic FCM',
        help='Nombre del topic (p. ej. difusión global: %s).' % FCM_TOPIC_ALL_USERS,
    )
    title = fields.Char(string='Título', required=True)
    body = fields.Text(string='Mensaje', required=True)
    app_route = fields.Char(
        string='Ruta en la app',
        help=(
            'Ruta interna de la SPA al pulsar la notificación '
            '(p. ej. /orders/42, /123, /orders). Vacío: el tap solo trae la app al frente.'
        ),
    )
    data_json = fields.Text(
        string='Datos adicionales (JSON)',
        help='Objeto JSON opcional; se envía como payload de datos FCM (valores como texto).',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if ctx.get('default_target_mode'):
            res['target_mode'] = ctx['default_target_mode']
        if ctx.get('default_partner_id'):
            res['partner_id'] = ctx['default_partner_id']
        if ctx.get('active_model') == 'res.partner' and ctx.get('active_ids'):
            skip_multi = bool(
                ctx.get('default_target_mode') == 'single_partner'
                and ctx.get('default_partner_id')
            )
            if not skip_multi:
                res['target_mode'] = 'multi_partner'
                res['partner_ids'] = [(6, 0, list(ctx['active_ids']))]
        return res

    def _parse_data_json(self):
        self.ensure_one()
        raw = (self.data_json or '').strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise UserError(_('JSON de datos no válido: %s') % e) from e
        if not isinstance(data, dict):
            raise UserError(_('El JSON de datos debe ser un objeto en el nivel raíz.'))
        return data

    def _merge_app_route(self, data):
        """Si app_route tiene texto, valida y fusiónalo como data['route']."""
        self.ensure_one()
        raw = (self.app_route or '').strip()
        if not raw:
            return data
        try:
            route = validate_app_route(raw)
        except ValueError:
            raise UserError(
                _(
                    'Ruta en la app no válida: %(route)s. '
                    'Debe empezar por / y no incluir esquema, //, .. ni espacios '
                    '(p. ej. /orders/42).'
                )
                % {'route': raw}
            ) from None
        merged = dict(data or {})
        merged['route'] = route
        return merged

    def action_send(self):
        self.ensure_one()
        data = self._merge_app_route(self._parse_data_json())
        fcm = self.env['order_bridge.fcm']
        if self.target_mode == 'single_partner':
            if not self.partner_id:
                raise UserError(_('Seleccione un contacto destinatario.'))
            result = fcm.send_to_partner(
                self.partner_id.id, self.title, self.body, data=data
            )
            msg = _('Enviado: %(batches)s lote(s), %(tokens)s token(s).') % {
                'batches': result['sent_batches'],
                'tokens': result['token_count'],
            }
        elif self.target_mode == 'multi_partner':
            if not self.partner_ids:
                raise UserError(_('Seleccione al menos un contacto.'))
            result = fcm.send_to_partner_ids(
                self.partner_ids.ids, self.title, self.body, data=data
            )
            msg = _('Enviado: %(batches)s lote(s), %(tokens)s token(s).') % {
                'batches': result['sent_batches'],
                'tokens': result['token_count'],
            }
        else:
            try:
                topic = validate_fcm_topic_string(self.fcm_topic or '')
            except ValueError as err:
                raise UserError(str(err)) from err
            fcm.send_to_topic(topic, self.title, self.body, data=data)
            msg = _('Notificación enviada al topic %s.') % topic
        close = {'type': 'ir.actions.act_window_close', 'infos': {'done': True}}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notificación push'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': close,
            },
        }
