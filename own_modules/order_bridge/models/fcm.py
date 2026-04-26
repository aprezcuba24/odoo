# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from collections.abc import Sequence

from odoo import api, models
from odoo.exceptions import UserError, AccessError
from odoo.tools.translate import _

from odoo.addons.order_bridge.utils import fcm_client

_logger = logging.getLogger(__name__)

# Quién puede enviar push: gestores de Tienda Apk o ventas.
_SEND_GROUPS = (
    'order_bridge.group_order_bridge_manager',
    'sales_team.group_sale_salesman',
)

FCM_MAX_BATCH = 500


class OrderBridgeFcm(models.AbstractModel):
    _name = 'order_bridge.fcm'
    _description = 'Envío de notificaciones FCM (uso interno Odoo)'

    def _order_bridge_ensure_fcm_send_access(self):
        if self.env.su:
            return
        if not any(self.env.user.has_group(g) for g in _SEND_GROUPS):
            raise AccessError(
                _('No tiene permisos para enviar notificaciones push.')
            )

    @api.model
    def send_to_partner(
        self,
        partner_id,
        title,
        body,
        data=None,
    ):
        """Notificación a un contacto: todos los tokens de dispositivos activos vinculados."""
        self._order_bridge_ensure_fcm_send_access()
        return self.send_to_partner_ids([partner_id], title, body, data=data)

    @api.model
    def send_to_partner_ids(
        self,
        partner_ids: Sequence,
        title: str,
        body: str,
        data: dict | None = None,
    ):
        """Notificación a varios contactos: tokens unificados, lotes de 500 (multicast FCM v1)."""
        self._order_bridge_ensure_fcm_send_access()
        pids = [int(p) for p in partner_ids if p]
        if not pids:
            return {'sent_batches': 0, 'token_count': 0}
        try:
            fcm_client.ensure_firebase_app()
        except fcm_client.FcmConfigurationError as e:
            raise UserError(_('FCM no está configurado: %s') % e) from e
        tokens = self.env['order_bridge.push_token'].order_bridge_tokens_for_partners(
            pids, active_devices_only=True
        )
        if not tokens:
            return {'sent_batches': 0, 'token_count': 0}
        batches = 0
        for batch in fcm_client.iter_token_batches(tokens, FCM_MAX_BATCH):
            fcm_client.send_notification_multicast(batch, title, body, data=data)
            batches += 1
        return {'sent_batches': batches, 'token_count': len(tokens)}

    @api.model
    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: dict | None = None,
    ):
        """Campaña por nombre de topic (p. ej. com_culabs_odooshop_all)."""
        self._order_bridge_ensure_fcm_send_access()
        if not (topic and str(topic).strip()):
            raise UserError(_('El topic FCM no puede estar vacío.'))
        try:
            fcm_client.ensure_firebase_app()
        except fcm_client.FcmConfigurationError as e:
            raise UserError(_('FCM no está configurado: %s') % e) from e
        return fcm_client.send_to_topic(
            str(topic).strip(), title, body, data=data
        )
