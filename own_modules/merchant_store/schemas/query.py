# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from odoo.addons.order_bridge.utils.constant import STORE_STATE_VALID_CHOICES


_STORE_STATE_KEYS = {key for key, _label in STORE_STATE_VALID_CHOICES}


def _params_to_dict(params: Any) -> dict[str, Any]:
    if hasattr(params, 'to_dict'):
        raw = params.to_dict(flat=True)
    else:
        raw = dict(params)
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None or value == '':
            continue
        out[str(key)] = value
    return out


class ProductsListQuery(BaseModel):
    model_config = ConfigDict(extra='ignore')

    limit: int = Field(default=80, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    merchant_id: int | None = Field(default=None, gt=0)
    search: str | None = None

    @field_validator('search')
    @classmethod
    def strip_search(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @classmethod
    def from_request_params(cls, params: Any) -> ProductsListQuery:
        return cls.model_validate(_params_to_dict(params))


class OrdersListQuery(BaseModel):
    model_config = ConfigDict(extra='ignore')

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    store_state: str | None = None

    @field_validator('store_state')
    @classmethod
    def validate_store_state(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if s not in _STORE_STATE_KEYS:
            raise ValueError(f'store_state inválido: {s}')
        return s

    @classmethod
    def from_request_params(cls, params: Any) -> OrdersListQuery:
        return cls.model_validate(_params_to_dict(params))


class PurchasesListQuery(BaseModel):
    model_config = ConfigDict(extra='ignore')

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @classmethod
    def from_request_params(cls, params: Any) -> PurchasesListQuery:
        return cls.model_validate(_params_to_dict(params))
