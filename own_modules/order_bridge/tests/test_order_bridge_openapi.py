# Part of Odoo. See LICENSE file for full copyright and licensing details.

import importlib.util
import json
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.order_bridge.schemas import responses as R


def _load_export_openapi():
    """Load ``scripts/export_openapi.py`` without treating ``scripts`` as a package."""
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'export_openapi.py'
    spec = importlib.util.spec_from_file_location('order_bridge_export_openapi', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('Cannot load export_openapi')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@tagged('post_install', '-at_install')
class TestOrderBridgeOpenapi(TransactionCase):
    def test_openapi_json_matches_generator(self):
        """Committed ``docs/openapi.json`` must match running ``export_openapi`` (update spec after API changes)."""
        mod = _load_export_openapi()
        generated = mod.build_spec(mod.load_order_bridge_schemas())
        committed_path = Path(__file__).resolve().parents[1] / 'docs' / 'openapi.json'
        committed = json.loads(committed_path.read_text(encoding='utf-8'))
        self.assertEqual(
            generated,
            committed,
            'Run: python3 own_modules/order_bridge/scripts/export_openapi.py',
        )
        static_path = Path(__file__).resolve().parents[1] / 'static' / 'openapi.json'
        self.assertTrue(static_path.is_file(), 'Run export_openapi.py to create static/openapi.json')
        self.assertEqual(
            committed_path.read_text(encoding='utf-8'),
            static_path.read_text(encoding='utf-8'),
            'docs/openapi.json and static/openapi.json must stay in sync',
        )

    def test_response_models_match_api_payloads(self):
        R.RegisterOkResponse.model_validate({
            'status': 'ok',
            'created': True,
            'partner_id': 42,
            'validated': False,
        })
        R.StatusResponse.model_validate({
            'validated': False,
            'phone': '+34600111222',
            'partner_name': 'Test',
            'partner_id': 1,
        })
        R.ProfileResponse.model_validate({
            'id': 1,
            'name': 'N',
            'phone': '+34000',
            'email': None,
            'address': None,
        })
        R.ProfileResponse.model_validate({
            'id': 1,
            'name': 'N',
            'phone': '+34000',
            'email': 'a@b.co',
            'address': {
                'street': 'S',
                'neighborhood': 'N',
                'municipality': 'M',
                'state': 'ST',
            },
        })
        R.CategoriesListResponse.model_validate({
            'items': [{'id': 1, 'name': 'C', 'parent_id': None}],
            'total': 1,
        })
        R.ProductsPageResponse.model_validate({
            'items': [{
                'id': 10,
                'name': 'P',
                'default_code': None,
                'list_price': 1.5,
                'uom_name': 'Units',
                'barcode': None,
                'pos_categories': [{'id': 2, 'name': 'PC'}],
            }],
            'limit': 80,
            'offset': 0,
            'total': 50,
            'pos_config_id': 3,
        })
        R.ProductDetailResponse.model_validate({
            'id': 10,
            'name': 'P',
            'default_code': 'REF',
            'list_price': 2.0,
            'uom_name': None,
            'barcode': False,
            'pos_categories': [{'id': 1, 'name': 'X'}],
            'description_sale': 'Long',
            'pos_config_id': 1,
        })
        R.OrdersPageResponse.model_validate({
            'items': [{
                'id': 5,
                'name': 'SO001',
                'order_ref': 'OB-00001',
                'origin': 'app',
                'state': 'draft',
                'date_order': '2025-01-01T12:00:00',
                'amount_total': 100.0,
                'currency': 'USD',
                'device_validated': True,
                'delivery_address': None,
            }],
            'limit': 50,
            'offset': 0,
            'total': 1,
        })
        R.SaleOrderDetailResponse.model_validate({
            'id': 5,
            'name': 'SO001',
            'order_ref': False,
            'origin': 'app',
            'state': 'draft',
            'date_order': None,
            'amount_total': 10.0,
            'currency': False,
            'device_validated': False,
            'delivery_address': {
                'street': 's',
                'neighborhood': 'n',
                'municipality': 'm',
                'state': 'st',
            },
            'lines': [{
                'product_id': 1,
                'name': 'Prod',
                'qty': 2.0,
                'price_unit': 5.0,
                'price_subtotal': 10.0,
            }],
        })
        R.OrderCreatedResponse.model_validate({
            'id': 1,
            'name': 'S',
            'order_ref': None,
            'state': 'draft',
            'device_validated': False,
            'delivery_address': None,
        })
        R.OrderCancelResponse.model_validate({'id': 1, 'state': 'cancel'})
        R.ValidationErrorResponse.model_validate({
            'error': 'validation',
            'message': 'Bad',
            'details': [{'loc': ['body', 'device_key'], 'msg': 'required', 'type': 'missing'}],
        })
        R.ValidationErrorResponse.model_validate({'error': 'validation', 'message': 'UserError'})
        R.UnauthorizedErrorResponse.model_validate({
            'error': 'unauthorized',
            'message': 'Invalid or missing device key',
        })
        R.SimpleErrorResponse.model_validate({'error': 'invalid_json'})
        R.ConfigurationErrorResponse.model_validate({
            'error': 'configuration',
            'message': 'No point of sale is linked',
        })
        R.MessageErrorResponse.model_validate({
            'error': 'forbidden',
            'message': 'only draft orders can be cancelled',
        })
