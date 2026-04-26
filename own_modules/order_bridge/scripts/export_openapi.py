#!/usr/bin/env python3
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Genera la especificación OpenAPI 3.1 para Tienda Apk a partir de modelos Pydantic (sin importar Odoo)."""

from __future__ import annotations

import importlib.util
import json
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _ensure_repo_and_addons_on_path():
    """Permite importar ``odoo.addons.order_bridge`` al generar la spec fuera de odoo-bin."""
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


def load_order_bridge_schemas():
    """Import ``order_bridge.schemas`` (requiere Odoo en path para ``responses``)."""
    _ensure_repo_and_addons_on_path()
    bridge_root = Path(__file__).resolve().parent.parent
    schema_dir = bridge_root / 'schemas'
    pkg_name = 'order_bridge_schemas_export'
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
            'application/json': {'schema': {'oneOf': [_ref(n) for n in names]}}
        },
    }


def build_spec(pkg_name: str) -> dict[str, Any]:
    bodies = import_module('.bodies', package=pkg_name)
    responses = import_module('.responses', package=pkg_name)

    models = _models_from_module(bodies) + _models_from_module(responses)
    components = {'schemas': merge_components(models)}
    components['securitySchemes'] = {
        'deviceBearer': {
            'type': 'http',
            'scheme': 'bearer',
            'description': 'Clave de dispositivo del registro (`Authorization: Bearer <device_key>`).',
        }
    }

    unauthorized = {'401': _ok('UnauthorizedErrorResponse', 'Clave de dispositivo no válida o ausente')}
    val_400 = {'400': _one_of(['ValidationErrorResponse', 'MessageErrorResponse'], 'Error de validación o regla de negocio')}
    val_400_body = {'400': _one_of(['ValidationErrorResponse', 'SimpleErrorResponse'], 'JSON no válido o error de validación')}
    orders_create_400 = {
        '400': _one_of(
            ['ValidationErrorResponse', 'SimpleErrorResponse', 'InsufficientStockErrorResponse'],
            'JSON no válido, stock insuficiente o error de validación',
        ),
    }
    not_found = {'404': _ok('SimpleErrorResponse', 'Recurso no encontrado')}
    config_503 = {
        '503': _ok('ConfigurationErrorResponse', 'FCM no configurado en el servidor (credenciales)'),
    }
    push_token_400 = {
        '400': _one_of(
            ['ValidationErrorResponse', 'MessageErrorResponse'],
            'Validación o token vacío',
        ),
    }
    push_topics_400 = {
        '400': _one_of(
            ['ValidationErrorResponse', 'MessageErrorResponse'],
            'Validación o sin token FCM registrado (usar POST /push/token antes)',
        ),
    }

    paths: dict[str, Any] = {
        '/api/order_bridge/register': {
            'post': {
                'summary': 'Registrar u obtener dispositivo',
                'operationId': 'order_bridge_register',
                'requestBody': {
                    'required': True,
                    'content': {'application/json': {'schema': _ref('RegisterBody')}},
                },
                'deprecated': False,
                'responses': {
                    '200': _ok('RegisterOkResponse'),
                    **val_400_body,
                },
            },
        },
        '/api/order_bridge/status': {
            'get': {
                'summary': 'Estado de validación del dispositivo',
                'operationId': 'order_bridge_status',
                'security': [{'deviceBearer': []}],
                'responses': {
                    '200': _ok('StatusResponse'),
                    **unauthorized,
                },
            },
        },
        '/api/order_bridge/profile': {
            'get': {
                'summary': 'Obtener perfil del contacto',
                'operationId': 'order_bridge_profile_get',
                'security': [{'deviceBearer': []}],
                'responses': {'200': _ok('ProfileResponse'), **unauthorized},
            },
            'put': {
                'summary': 'Sustituir perfil (dirección completa)',
                'operationId': 'order_bridge_profile_put',
                'security': [{'deviceBearer': []}],
                'requestBody': {
                    'required': True,
                    'content': {'application/json': {'schema': _ref('ProfilePutBody')}},
                },
                'responses': {
                    '200': _ok('ProfileResponse'),
                    **unauthorized,
                    **val_400_body,
                },
            },
            'patch': {
                'summary': 'Actualización parcial del perfil',
                'operationId': 'order_bridge_profile_patch',
                'security': [{'deviceBearer': []}],
                'requestBody': {
                    'required': True,
                    'content': {'application/json': {'schema': _ref('ProfilePatchBody')}},
                },
                'responses': {
                    '200': _ok('ProfileResponse'),
                    **unauthorized,
                    **val_400_body,
                },
            },
        },
        '/api/order_bridge/push/token': {
            'post': {
                'summary': 'Registrar o actualizar token FCM y suscribir topics',
                'operationId': 'order_bridge_push_token',
                'security': [{'deviceBearer': []}],
                'requestBody': {
                    'required': True,
                    'content': {'application/json': {'schema': _ref('PushTokenBody')}},
                },
                'responses': {
                    '200': _ok('PushTopicsOkResponse'),
                    **unauthorized,
                    **val_400_body,
                    '503': _ok('ConfigurationErrorResponse', 'FCM no configurado (credenciales)'),
                },
            },
        },
        '/api/order_bridge/push/topics': {
            'patch': {
                'summary': 'Cambiar suscripciones a topics FCM (requiere token previo vía POST /push/token)',
                'operationId': 'order_bridge_push_topics',
                'security': [{'deviceBearer': []}],
                'requestBody': {
                    'required': True,
                    'content': {'application/json': {'schema': _ref('PushTopicsPatchBody')}},
                },
                'responses': {
                    '200': _ok('PushTopicsOkResponse'),
                    **unauthorized,
                    '400': _one_of(
                        ['ValidationErrorResponse', 'MessageErrorResponse'],
                        'Error de validación o token FCM no registrado previamente',
                    ),
                    '503': _ok('ConfigurationErrorResponse', 'FCM no configurado (credenciales)'),
                },
            },
        },
        '/api/order_bridge/categories': {
            'get': {
                'summary': 'Categorías de producto del catálogo',
                'operationId': 'order_bridge_categories',
                'responses': {
                    '200': _ok('CategoriesListResponse'),
                },
            },
        },
        '/api/order_bridge/municipalities': {
            'get': {
                'summary': 'Municipios con barrios (nomencladores Tienda Apk)',
                'operationId': 'order_bridge_municipalities',
                'responses': {
                    '200': _ok('MunicipalitiesListResponse'),
                },
            },
        },
        '/api/order_bridge/settings': {
            'get': {
                'summary': 'Datos generales de la tienda (teléfono, etc.)',
                'operationId': 'order_bridge_settings',
                'responses': {
                    '200': _ok('GeneralSettingsResponse'),
                },
            },
        },
        '/api/order_bridge/banners': {
            'get': {
                'summary': 'Banners publicitarios activos del catálogo',
                'operationId': 'order_bridge_banners',
                'responses': {
                    '200': _ok('BannersListResponse'),
                },
            },
        },
        '/api/order_bridge/products': {
            'get': {
                'summary': 'Listado de productos (paginado)',
                'operationId': 'order_bridge_products',
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
                        'name': 'category_id',
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
                    '200': _ok('ProductsPageResponse'),
                    **val_400,
                },
            },
        },
        '/api/order_bridge/products/{product_id}': {
            'get': {
                'summary': 'Detalle de producto',
                'operationId': 'order_bridge_product_detail',
                'parameters': [
                    {
                        'name': 'product_id',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                    },
                ],
                'responses': {
                    '200': _ok('ProductDetailResponse'),
                    **not_found,
                },
            },
        },
        '/api/order_bridge/orders': {
            'get': {
                'summary': 'Listar pedidos del contacto del dispositivo',
                'operationId': 'order_bridge_orders_list',
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
                    {'name': 'state', 'in': 'query', 'required': False, 'schema': {'type': 'string'}},
                ],
                'responses': {
                    '200': _ok('OrdersPageResponse'),
                    **unauthorized,
                    **val_400,
                },
            },
            'post': {
                'summary': 'Crear pedido de venta',
                'operationId': 'order_bridge_orders_create',
                'security': [{'deviceBearer': []}],
                'requestBody': {
                    'required': True,
                    'content': {'application/json': {'schema': _ref('OrderCreateBody')}},
                },
                'responses': {
                    '200': _ok('OrderCreatedResponse'),
                    **unauthorized,
                    **orders_create_400,
                },
            },
        },
        '/api/order_bridge/orders/{order_id}': {
            'get': {
                'summary': 'Detalle del pedido con líneas',
                'operationId': 'order_bridge_order_detail',
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
                    '200': _ok('SaleOrderDetailResponse'),
                    **unauthorized,
                    **not_found,
                },
            },
        },
        '/api/order_bridge/orders/{order_id}/cancel': {
            'post': {
                'summary': 'Cancelar pedido en borrador',
                'operationId': 'order_bridge_order_cancel',
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
                    '200': _ok('OrderCancelResponse'),
                    **unauthorized,
                    **not_found,
                    **val_400,
                },
            },
        },
    }

    return {
        'openapi': '3.1.0',
        'info': {
            'title': 'API Tienda Apk',
            'version': '19.0.2.0.17',
            'description': 'API REST JSON para clientes externos bajo `/api/order_bridge/`. '
            'Autenticación con clave de dispositivo (Bearer), salvo `POST /register` y las peticiones GET públicas del catálogo '
            '(`/categories`, `/municipalities`, `/settings`, `/banners`, `/products`, `/products/{id}`).',
        },
        'paths': paths,
        'components': components,
        'tags': [{'name': 'order_bridge', 'description': 'API de dispositivos y catálogo Tienda Apk'}],
    }


def main() -> None:
    pkg = load_order_bridge_schemas()
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
