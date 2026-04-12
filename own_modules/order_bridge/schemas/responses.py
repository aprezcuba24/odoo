# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _odoo_falsy_str(v: Any) -> str | None:
    if v is None or v is False:
        return None
    return str(v) if v is not None else None


class RegisterOkResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: str = Field(..., description="Siempre 'ok' si tiene éxito")
    created: bool
    partner_id: int
    validated: bool


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    validated: bool
    phone: str | None = None
    partner_name: str
    partner_id: int

    @field_validator('phone', mode='before')
    @classmethod
    def phone_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class ProfileAddressOut(BaseModel):
    model_config = ConfigDict(extra='forbid')

    street: str
    municipality_id: int | None = None
    municipality_name: str | None = None
    neighborhood_id: int | None = None
    neighborhood_name: str | None = None
    state: str

    @field_validator('municipality_name', 'neighborhood_name', mode='before')
    @classmethod
    def name_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    phone: str
    email: str | None = None
    address: ProfileAddressOut | None = None

    @field_validator('email', mode='before')
    @classmethod
    def email_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class GeneralSettingsResponse(BaseModel):
    """`GET /api/order_bridge/settings` — datos generales de la tienda (catálogo)."""

    model_config = ConfigDict(extra='forbid')

    shop_phone: str | None = None

    @field_validator('shop_phone', mode='before')
    @classmethod
    def shop_phone_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class ProductCategoryRow(BaseModel):
    """`product.category` row in `GET /categories` or embedded on a product (`category`)."""

    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    parent_id: int | None = None


class CategoriesListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[ProductCategoryRow]
    total: int


class ProductListRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    default_code: str | None = None
    list_price: float
    uom_name: str | None = None
    barcode: str | None = None
    category: ProductCategoryRow | None = None

    @field_validator('default_code', 'uom_name', 'barcode', mode='before')
    @classmethod
    def char_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class ProductDetailResponse(ProductListRow):
    """Single product with long description."""

    model_config = ConfigDict(extra='forbid')

    description_sale: str | None = None

    @field_validator('description_sale', mode='before')
    @classmethod
    def desc_falsy(cls, v: Any) -> str | None:
        s = _odoo_falsy_str(v)
        return s


class PaginationMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')

    limit: int
    offset: int
    total: int


class ProductsPageResponse(PaginationMeta):
    model_config = ConfigDict(extra='forbid')

    items: list[ProductListRow]


class DeliveryAddressOut(BaseModel):
    model_config = ConfigDict(extra='forbid')

    street: str
    municipality_id: int | None = None
    municipality_name: str | None = None
    neighborhood_id: int | None = None
    neighborhood_name: str | None = None
    state: str

    @field_validator('municipality_name', 'neighborhood_name', mode='before')
    @classmethod
    def name_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class NeighborhoodRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str


class MunicipalityWithNeighborhoodsRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    neighborhoods: list[NeighborhoodRow]


class MunicipalitiesListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[MunicipalityWithNeighborhoodsRow]
    total: int


class SaleOrderSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    order_ref: str | None = None
    origin: str
    state: str
    date_order: str | None = None
    amount_total: float
    currency: str | None = None
    device_validated: bool
    delivery_address: DeliveryAddressOut | None = None

    @field_validator('order_ref', 'currency', mode='before')
    @classmethod
    def falsy_to_none(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class SaleOrderLineOut(BaseModel):
    model_config = ConfigDict(extra='forbid')

    product_id: int
    name: str
    qty: float
    price_unit: float
    price_subtotal: float
    qty_delivered: float
    qty_reserved: float


class SaleOrderDetailResponse(SaleOrderSummary):
    model_config = ConfigDict(extra='forbid')

    lines: list[SaleOrderLineOut]


class OrdersPageResponse(PaginationMeta):
    model_config = ConfigDict(extra='forbid')

    items: list[SaleOrderSummary]


class OrderCreatedResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    order_ref: str | None = None
    state: str
    device_validated: bool
    delivery_address: DeliveryAddressOut | None = None

    @field_validator('order_ref', mode='before')
    @classmethod
    def order_ref_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class OrderCancelResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    state: str


class ValidationDetailItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    loc: list[str]
    msg: str
    type: str


class InsufficientStockProductItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    product_id: int = Field(..., description='Variante de producto (`product.product`)')
    available_qty: float = Field(..., description='Cantidad disponible en el almacén del catálogo')


class InsufficientStockErrorResponse(BaseModel):
    """Stock insuficiente al validar líneas del POST crear pedido."""

    model_config = ConfigDict(extra='forbid')

    error: str = Field(default='insufficient_stock', description="Código fijo 'insufficient_stock'")
    message: str = Field(..., description='Mensaje resumido')
    products: list[InsufficientStockProductItem] = Field(
        ...,
        description='Productos almacenables con cantidad libre inferior a la solicitada',
    )


class ValidationErrorResponse(BaseModel):
    """Pydantic validation errors include ``details``; some handlers return only ``message``."""

    model_config = ConfigDict(extra='forbid')

    error: str = Field(..., description="Normalmente 'validation'")
    message: str
    details: list[ValidationDetailItem] | None = None


class UnauthorizedErrorResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    error: str = Field(..., description="Normalmente 'unauthorized'")
    message: str


class SimpleErrorResponse(BaseModel):
    """e.g. invalid_json, not_found."""

    model_config = ConfigDict(extra='forbid')

    error: str


class ConfigurationErrorResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    error: str = Field(..., description="Normalmente 'configuration'")
    message: str


class MessageErrorResponse(BaseModel):
    """e.g. forbidden with a message."""

    model_config = ConfigDict(extra='forbid')

    error: str
    message: str
