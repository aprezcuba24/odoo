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
from .responses import (
    CategoriesListResponse,
    ConfigurationErrorResponse,
    MessageErrorResponse,
    OrderCancelResponse,
    OrderCreatedResponse,
    OrdersPageResponse,
    ProductDetailResponse,
    ProductsPageResponse,
    ProfileResponse,
    RegisterOkResponse,
    SaleOrderDetailResponse,
    SimpleErrorResponse,
    StatusResponse,
    UnauthorizedErrorResponse,
    ValidationErrorResponse,
)

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
    'RegisterOkResponse',
    'SaleOrderDetailResponse',
    'SimpleErrorResponse',
    'StatusResponse',
    'UnauthorizedErrorResponse',
    'ValidationErrorResponse',
    'CategoriesListResponse',
    'ConfigurationErrorResponse',
    'MessageErrorResponse',
    'OrderCancelResponse',
    'OrderCreatedResponse',
    'OrdersPageResponse',
    'ProductDetailResponse',
    'ProductsPageResponse',
    'ProfileResponse',
    'pydantic_errors_to_api_body',
]
