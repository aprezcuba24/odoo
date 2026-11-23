# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CheckoutLineIn(BaseModel):
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


class CheckoutCreateBody(BaseModel):
    model_config = ConfigDict(extra='forbid')

    client_checkout_id: str = Field(..., min_length=1, max_length=64)
    lines: list[CheckoutLineIn] = Field(..., min_length=1)
    order_bridge_order_id: int | None = Field(default=None, gt=0)

    @field_validator('client_checkout_id')
    @classmethod
    def client_checkout_id_not_blank(cls, v: str) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError('client_checkout_id no puede estar vacío')
        return s
