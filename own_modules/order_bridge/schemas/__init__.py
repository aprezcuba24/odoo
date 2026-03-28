# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .bodies import (
    AddressFull,
    AddressPatch,
    OrderCreateBody,
    OrderLineIn,
    ProfilePatchBody,
    ProfilePutBody,
    RegisterBody,
)
from .errors import pydantic_errors_to_api_body
from .query import OrdersListQuery, ProductsListQuery

__all__ = [
    'AddressFull',
    'AddressPatch',
    'OrderCreateBody',
    'OrderLineIn',
    'OrdersListQuery',
    'ProductsListQuery',
    'ProfilePatchBody',
    'ProfilePutBody',
    'RegisterBody',
    'pydantic_errors_to_api_body',
]
