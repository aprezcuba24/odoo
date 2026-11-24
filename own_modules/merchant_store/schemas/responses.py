# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from odoo.addons.order_bridge.schemas.responses import SaleOrderSummary
from odoo.addons.order_bridge.utils.constant import DEFAULT_STORE_STATE, STORE_STATE_VALID


def _odoo_falsy_str(v: Any) -> str | None:
    if v is None or v is False:
        return None
    return str(v) if v is not None else None


class MerchantRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    description: str | None = None
    logo_url: str | None = None
    logo_thumbnail_url: str | None = None

    @field_validator('description', mode='before')
    @classmethod
    def description_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class MerchantsListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[MerchantRow]
    total: int


class MerchantProductListRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    list_price: float
    merchant_id: int
    uom_name: str | None = None
    image_url: str | None = None
    image_thumbnail_url: str | None = None

    @field_validator('uom_name', mode='before')
    @classmethod
    def uom_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class MerchantProductDetailResponse(MerchantProductListRow):
    model_config = ConfigDict(extra='forbid')

    description_sale: str | None = None

    @field_validator('description_sale', mode='before')
    @classmethod
    def desc_falsy(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class MerchantProductsPageResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[MerchantProductListRow]
    limit: int
    offset: int
    total: int


class MerchantOrderLineOut(BaseModel):
    model_config = ConfigDict(extra='forbid')

    product_id: int
    name: str
    qty: float
    price_unit: float
    price_subtotal: float
    image_url: str | None = None
    image_thumbnail_url: str | None = None


class MerchantOrderSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: int
    name: str
    merchant_id: int
    merchant_name: str
    client_checkout_id: str | None = None
    order_bridge_order_id: int | None = None
    state: str
    store_state: STORE_STATE_VALID
    date_order: str | None = None
    amount_total: float
    currency: str | None = None

    @field_validator('client_checkout_id', 'currency', mode='before')
    @classmethod
    def falsy_to_none(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)

    @field_validator('order_bridge_order_id', mode='before')
    @classmethod
    def falsy_id(cls, v: Any) -> int | None:
        if v is None or v is False:
            return None
        return int(v)

    @field_validator('store_state', mode='before')
    @classmethod
    def store_state_str(cls, v: Any) -> str:
        return str(v) if v is not None else DEFAULT_STORE_STATE


class MerchantOrderDetailResponse(MerchantOrderSummary):
    model_config = ConfigDict(extra='forbid')

    lines: list[MerchantOrderLineOut]


class MerchantOrdersPageResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[MerchantOrderSummary]
    limit: int
    offset: int
    total: int


class CheckoutCreatedResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    client_checkout_id: str
    orders: list[MerchantOrderDetailResponse]


class MerchantPurchaseRow(BaseModel):
    model_config = ConfigDict(extra='forbid')

    purchase_key: str
    client_checkout_id: str | None = None
    date_order: str | None = None
    amount_total: float
    currency: str | None = None
    order: SaleOrderSummary | None = None
    suborders: list[MerchantOrderSummary]

    @field_validator('client_checkout_id', 'currency', mode='before')
    @classmethod
    def purchase_falsy_to_none(cls, v: Any) -> str | None:
        return _odoo_falsy_str(v)


class MerchantPurchasesPageResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    items: list[MerchantPurchaseRow]
    limit: int
    offset: int
    total: int


class SimpleErrorResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    error: str


class MessageErrorResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    error: str
    message: str
