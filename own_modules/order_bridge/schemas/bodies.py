# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from odoo.addons.order_bridge.utils.fcm_topic import (
    validate_fcm_topic_string as _valid_fcm_topic,
)


class RegisterBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_key: str = Field(..., min_length=1)
    phone: str | None = None
    device_info: str | None = None

    @field_validator('phone')
    @classmethod
    def phone_eight_digits(cls, v: str | None) -> str | None:
        s = str(v).strip()
        if not s.isdigit() or len(s) != 8:
            raise ValueError('El teléfono debe tener 8 dígitos')
        return s


class AddressFull(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    street: str = Field(..., min_length=1)
    municipality_id: int = Field(..., gt=0)
    neighborhood_id: int = Field(..., gt=0)
    state: str = Field(..., min_length=1)


class ProfilePutBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(..., min_length=1)
    address: AddressFull


class AddressPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    street: str | None = None
    municipality_id: int | None = Field(
        default=None,
        description='Tras el merge con la dirección guardada, municipio y barrio deben quedar definidos.',
    )
    neighborhood_id: int | None = Field(
        default=None,
        description='Tras el merge con la dirección guardada, municipio y barrio deben quedar definidos.',
    )
    state: str | None = None

    @field_validator('municipality_id', 'neighborhood_id')
    @classmethod
    def positive_id_if_set(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v < 1:
            raise ValueError('el id debe ser mayor que cero')
        return v


class ProfilePatchBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str | None = None
    address: AddressPatch | None = None

    @field_validator('name')
    @classmethod
    def name_not_empty_if_present(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = str(v).strip()
        if not s:
            raise ValueError('el nombre no puede estar vacío')
        return s


class OrderLineIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    product_id: int = Field(gt=0)
    qty: float = Field(gt=0)

    @model_validator(mode='before')
    @classmethod
    def pick_qty(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        q = data.get('qty')
        if q is None:
            q = data.get('product_uom_qty')
        out = {k: v for k, v in data.items() if k not in ('qty', 'product_uom_qty')}
        out['qty'] = q
        return out


class OrderCreateBody(BaseModel):
    model_config = ConfigDict(extra='forbid')

    lines: list[OrderLineIn] = Field(..., min_length=1)

    @model_validator(mode='after')
    def check_stock(self, info: ValidationInfo) -> OrderCreateBody:
        ctx = info.context
        if not ctx:
            return self
        env = ctx.get('env')
        catalog_company = ctx.get('catalog_company')
        product_domain = ctx.get('product_domain')
        if not env or not catalog_company or product_domain is None:
            return self
        # Deferred import so ``schemas`` can load in export_openapi without package parents.
        from odoo.addons.order_bridge.utils import order_stock

        order_stock.validate_order_lines_stock(env, catalog_company, product_domain, self.lines)
        return self


class PushTokenBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    fcm_token: str = Field(...)
    platform: Literal['android', 'ios']
    subscribe_topics: list[str] = Field(default_factory=list)

    @field_validator('fcm_token')
    @classmethod
    def fcm_token_not_empty(cls, v: str) -> str:
        s = (v or '').strip()
        if not s:
            raise ValueError('El fcm_token no puede estar vacío')
        return s

    @field_validator('subscribe_topics')
    @classmethod
    def validate_subscribe_topics(cls, v: list[str]) -> list[str]:
        for t in v:
            _valid_fcm_topic(t)
        return v


class PushTopicsPatchBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    subscribe_topics: list[str] = Field(default_factory=list)
    unsubscribe_topics: list[str] = Field(default_factory=list)

    @field_validator('subscribe_topics', 'unsubscribe_topics')
    @classmethod
    def validate_topic_strings(cls, v: list[str]) -> list[str]:
        for t in v:
            _valid_fcm_topic(t)
        return v
