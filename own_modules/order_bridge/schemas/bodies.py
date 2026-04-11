# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    neighborhood: str = Field(..., min_length=1)
    municipality: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)


class ProfilePutBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(..., min_length=1)
    address: AddressFull


class AddressPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    street: str | None = None
    neighborhood: str | None = None
    municipality: str | None = None
    state: str | None = None


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
