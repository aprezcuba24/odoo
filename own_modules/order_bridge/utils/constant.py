from typing import Literal

# Topic fijo usado por la app odoo-shop para difusiones a todos los usuarios.
FCM_TOPIC_ALL_USERS = 'com_culabs_odooshop_all'

STATE_REVIEWING = 'reviewing'
STATE_NEGOTIATING = 'negotiating'
STATE_READY_FOR_DELIVERY = 'ready_for_delivery'
STATE_DELIVERED = 'delivered'
STATE_CANCELED = 'canceled'

STORE_STATE_VALID = Literal[
    STATE_REVIEWING,
    STATE_NEGOTIATING,
    STATE_READY_FOR_DELIVERY,
    STATE_DELIVERED,
    STATE_CANCELED,
]
DEFAULT_STORE_STATE: STORE_STATE_VALID = STATE_REVIEWING

STORE_STATE_VALID_CHOICES = [
    (STATE_REVIEWING, 'Revisando'),
    (STATE_NEGOTIATING, 'Negociando'),
    (STATE_READY_FOR_DELIVERY, 'Listo para entrega'),
    (STATE_DELIVERED, 'Entregado'),
    (STATE_CANCELED, 'Cancelado'),
]

STORE_STATE_COLOR: dict[str, str] = {
    STATE_REVIEWING: 'secondary',
    STATE_NEGOTIATING: 'warning',
    STATE_READY_FOR_DELIVERY: 'info',
    STATE_DELIVERED: 'success',
    STATE_CANCELED: 'danger',
}


def store_state_btn_class(state: str, *, outline: bool = False) -> str:
    color = STORE_STATE_COLOR[state]
    prefix = 'btn-outline-' if outline else 'btn-'
    return f'{prefix}{color}'


def store_state_badge_decoration(state: str) -> str:
    """Decoration name for widget badge in XML views."""
    color = STORE_STATE_COLOR[state]
    return 'muted' if color == 'secondary' else color


ORDER_BRIDGE_ALLOWED_STORE_TRANSITIONS = {
    STATE_REVIEWING: {STATE_NEGOTIATING, STATE_READY_FOR_DELIVERY, STATE_CANCELED},
    STATE_NEGOTIATING: {STATE_READY_FOR_DELIVERY, STATE_CANCELED},
    STATE_READY_FOR_DELIVERY: {STATE_DELIVERED, STATE_CANCELED},
    STATE_DELIVERED: {STATE_CANCELED},
    STATE_CANCELED: set(),
}