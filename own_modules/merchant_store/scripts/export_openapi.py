#!/usr/bin/env python3
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Genera la especificación OpenAPI 3.1 para Comercios a partir de modelos Pydantic (sin importar Odoo)."""

from __future__ import annotations

import importlib.util
import json
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _ensure_repo_and_addons_on_path():
    """Permite importar ``odoo.addons.*`` al generar la spec fuera de odoo-bin."""
    repo = Path(__file__).resolve().parent.parent.parent.parent
    rs = str(repo)
    if rs not in sys.path:
        sys.path.insert(0, rs)
    import odoo.addons  # noqa: PLC0415

    paths = list(odoo.addons.__path__)
    for rel in ('own_modules', 'addons'):
        p = str(repo / rel)
        if p not in paths:
            paths.append(p)
    odoo.addons.__path__ = paths  # type: ignore[misc]


def load_merchant_store_schemas():
    """Import ``merchant_store.schemas`` sin requerir ``odoo-bin``."""
    _ensure_repo_and_addons_on_path()
    module_root = Path(__file__).resolve().parent.parent
    schema_dir = module_root / 'schemas'
    pkg_name = 'merchant_store_schemas_export'
    spec = importlib.util.spec_from_file_location(
        pkg_name,
        schema_dir / '__init__.py',
        submodule_search_locations=[str(schema_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError('Cannot load schemas package')
    pkg = importlib.util.module_from_spec(spec)
    pkg.__path__ = [str(schema_dir)]
    pkg.__name__ = pkg_name
    pkg.__package__ = pkg_name
    sys.modules[pkg_name] = pkg
    spec.loader.exec_module(pkg)
    return pkg_name


def _models_from_module(module: object) -> list[type[BaseModel]]:
    out: list[type[BaseModel]] = []
    for attr in sorted(dir(module)):
        obj = getattr(module, attr)
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
            out.append(obj)
    return out


def merge_components(models: list[type[BaseModel]]) -> dict[str, Any]:
    """Flatten Pydantic JSON schemas into OpenAPI ``components/schemas``."""
    registry: dict[str, Any] = {}
    for m in models:
        name = m.__name__
        schema = m.model_json_schema(ref_template='#/components/schemas/{model}')
        defs = schema.pop('$defs', None) or {}
        for dname, dschema in defs.items():
            if dname not in registry:
                registry[dname] = dschema
        registry[name] = schema
    return registry


def _ref(name: str) -> dict[str, str]:
    return {'$ref': f'#/components/schemas/{name}'}


def _ok(schema_name: str, description: str | None = None) -> dict[str, Any]:
    return {
        'description': description or 'Respuesta correcta',
        'content': {'application/json': {'schema': _ref(schema_name)}},
    }


def _one_of(names: list[str], description: str) -> dict[str, Any]:
    return {
        'description': description,
        'content': {
            'application/json': {'schema': {'oneOf': [_ref(n) for n in names]}},
        },
    }


def build_spec(pkg_name: str) -> dict[str, Any]:
    bodies = import_module('.bodies', package=pkg_name)
    responses = import_module('.responses', package=pkg_name)
    bridge_responses = import_module('odoo.addons.order_bridge.schemas.responses')
    bridge_constants = import_module('odoo.addons.order_bridge.utils.constant')

    models = (
        _models_from_module(bodies)
        + _models_from_module(responses)
        + [
            bridge_responses.UnauthorizedErrorResponse,
            bridge_responses.ValidationErrorResponse,
        ]
    )
    components: dict[str, Any] = {'schemas': merge_components(models)}
    components['securitySchemes'] = {
        'deviceBearer': {
            'type': 'http',
            'scheme': 'bearer',
            'description': 'Clave de dispositivo del registro de Tienda Apk (`Authorization: Bearer <device_key>`).',
        },
    }

    unauthorized = {
        '401': _ok('UnauthorizedErrorResponse', 'Clave de dispositivo no válida o ausente'),
    }
    not_found = {
        '404': _ok(
            'SimpleErrorResponse',
            'Recurso no encontrado o app Comercios desactivada para la compañía',
        ),
    }
    val_400_query = {
        '400': _ok('ValidationErrorResponse', 'Parámetros de consulta no válidos'),
    }
    val_400_checkout = {
        '400': _one_of(
            ['ValidationErrorResponse', 'SimpleErrorResponse', 'MessageErrorResponse'],
            'JSON no válido, error de validación o regla de negocio',
        ),
    }
    conflict_409 = {
        '409': _ok('SimpleErrorResponse', 'Conflicto de concurrencia al crear el checkout'),
    }
    store_state_enum = [key for key, _label in bridge_constants.STORE_STATE_VALID_CHOICES]

    paths: dict[str, Any] = {
        '/api/merchant_store/merchants': {
            'get': {
                'summary': 'Listar comerciantes activos de la compañía del dispositivo',
                'operationId': 'merchant_store_merchants_list',
                'security': [{'deviceBearer': []}],
                'responses': {
                    '200': _ok('MerchantsListResponse'),
                    **unauthorized,
                    **not_found,
                },
            },
        },
        '/api/merchant_store/merchants/{merchant_id}': {
            'get': {
                'summary': 'Detalle de un comerciante activo',
                'operationId': 'merchant_store_merchant_detail',
                'security': [{'deviceBearer': []}],
                'parameters': [
                    {
                        'name': 'merchant_id',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                    },
                ],
                'responses': {
                    '200': _ok('MerchantRow'),
                    **unauthorized,
                    **not_found,
                },
            },
        },
        '/api/merchant_store/products': {
            'get': {
                'summary': 'Listado de productos de comerciantes (paginado)',
                'operationId': 'merchant_store_products_list',
                'security': [{'deviceBearer': []}],
                'parameters': [
                    {
                        'name': 'limit',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer', 'minimum': 1, 'maximum': 200, 'default': 80},
                    },
                    {
                        'name': 'offset',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer', 'minimum': 0, 'default': 0},
                    },
                    {
                        'name': 'merchant_id',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer', 'exclusiveMinimum': 0},
                    },
                    {
                        'name': 'search',
                        'in': 'query',
                        'required': False,
                        'description': 'Búsqueda por nombre de producto (coincidencia parcial, sin distinción de mayúsculas)',
                        'schema': {'type': 'string'},
                    },
                ],
                'responses': {
                    '200': _ok('MerchantProductsPageResponse'),
                    **val_400_query,
                    **unauthorized,
                    **not_found,
                },
            },
        },
        '/api/merchant_store/products/{product_id}': {
            'get': {
                'summary': 'Detalle de producto de comerciante',
                'operationId': 'merchant_store_product_detail',
                'security': [{'deviceBearer': []}],
                'parameters': [
                    {
                        'name': 'product_id',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                    },
                ],
                'responses': {
                    '200': _ok('MerchantProductDetailResponse'),
                    **unauthorized,
                    **not_found,
                },
            },
        },
        '/api/merchant_store/checkouts': {
            'post': {
                'summary': 'Crear checkout de comerciantes (una suborden por comerciante)',
                'description': (
                    'Crea una suborden por cada comerciante presente en `lines`. '
                    'Idempotente por `client_checkout_id`: reutilizar el mismo identificador '
                    'en reintentos devuelve las subórdenes ya creadas sin duplicarlas.'
                ),
                'operationId': 'merchant_store_checkouts_create',
                'security': [{'deviceBearer': []}],
                'requestBody': {
                    'required': True,
                    'content': {'application/json': {'schema': _ref('CheckoutCreateBody')}},
                },
                'responses': {
                    '200': _ok('CheckoutCreatedResponse'),
                    **val_400_checkout,
                    **unauthorized,
                    **not_found,
                    **conflict_409,
                },
            },
        },
        '/api/merchant_store/orders': {
            'get': {
                'summary': 'Listar subórdenes de comerciantes del cliente',
                'operationId': 'merchant_store_orders_list',
                'security': [{'deviceBearer': []}],
                'parameters': [
                    {
                        'name': 'limit',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer', 'minimum': 1, 'maximum': 200, 'default': 50},
                    },
                    {
                        'name': 'offset',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer', 'minimum': 0, 'default': 0},
                    },
                    {
                        'name': 'store_state',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'string', 'enum': store_state_enum},
                    },
                ],
                'responses': {
                    '200': _ok('MerchantOrdersPageResponse'),
                    **val_400_query,
                    **unauthorized,
                    **not_found,
                },
            },
        },
        '/api/merchant_store/orders/{order_id}': {
            'get': {
                'summary': 'Detalle de una suborden con sus líneas',
                'operationId': 'merchant_store_order_detail',
                'security': [{'deviceBearer': []}],
                'parameters': [
                    {
                        'name': 'order_id',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                    },
                ],
                'responses': {
                    '200': _ok('MerchantOrderDetailResponse'),
                    **unauthorized,
                    **not_found,
                },
            },
        },
        '/api/merchant_store/purchases': {
            'get': {
                'summary': 'Listar historial de órdenes del cliente (tienda y comercios)',
                'description': (
                    'Historial plano para la app: devuelve cada pedido de Tienda Apk '
                    '(`source: "store"`) y cada orden de comerciante (`source: "merchant"`) '
                    'como una fila independiente ordenada por `date_order` descendente. '
                    'Ambas variantes incluyen `order.delivery_address` con la dirección '
                    'congelada al crear el pedido.'
                ),
                'operationId': 'merchant_store_purchases_list',
                'security': [{'deviceBearer': []}],
                'parameters': [
                    {
                        'name': 'limit',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer', 'minimum': 1, 'maximum': 200, 'default': 50},
                    },
                    {
                        'name': 'offset',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer', 'minimum': 0, 'default': 0},
                    },
                ],
                'responses': {
                    '200': _ok('MerchantPurchasesPageResponse'),
                    **val_400_query,
                    **unauthorized,
                    **not_found,
                },
            },
        },
    }

    return {
        'openapi': '3.1.0',
        'info': {
            'title': 'API Comercios',
            'version': '19.0.1.9.0',
            'description': (
                'API REST JSON para productos y subórdenes de comerciantes externos bajo '
                '`/api/merchant_store/`. Autenticación con la clave de dispositivo de Tienda Apk '
                '(Bearer). La compañía es la del dispositivo; estas rutas no leen `X-Company-Slug`.'
            ),
        },
        'paths': paths,
        'components': components,
        'tags': [{'name': 'merchant_store', 'description': 'API de comerciantes, catálogo y subórdenes'}],
    }


def main() -> None:
    pkg = load_merchant_store_schemas()
    spec = build_spec(pkg)
    text = json.dumps(spec, indent=2, sort_keys=True) + '\n'
    root = Path(__file__).resolve().parent.parent
    for rel in ('docs/openapi.json', 'static/openapi.json'):
        out = root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
        print(f'Wrote {out}')


if __name__ == '__main__':
    main()
