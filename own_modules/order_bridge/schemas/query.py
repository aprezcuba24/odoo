# Part of Odoo. See LICENSE file for full copyright and licensing details.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _params_to_dict(params: Any) -> dict[str, Any]:
    """Normalize Odoo werkzeug MultiDict-like params to a plain dict."""
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


class OrdersListQuery(BaseModel):
    model_config = ConfigDict(extra='ignore')

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    state: str | None = None

    @field_validator('state')
    @classmethod
    def strip_state(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @classmethod
    def from_request_params(cls, params: Any) -> OrdersListQuery:
        return cls.model_validate(_params_to_dict(params))


class ProductsListQuery(BaseModel):
    model_config = ConfigDict(extra='ignore')

    limit: int = Field(default=80, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    category_id: int | None = Field(default=None, gt=0)
    pos_category_id: int | None = Field(default=None, gt=0)

    @classmethod
    def from_request_params(cls, params: Any) -> ProductsListQuery:
        return cls.model_validate(_params_to_dict(params))
