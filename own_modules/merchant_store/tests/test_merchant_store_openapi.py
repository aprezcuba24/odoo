# Part of Odoo. See LICENSE file for full copyright and licensing details.

import importlib.util
import json
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged


def _load_export_openapi():
    """Load ``scripts/export_openapi.py`` without treating ``scripts`` as a package."""
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'export_openapi.py'
    spec = importlib.util.spec_from_file_location('merchant_store_export_openapi', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('Cannot load export_openapi')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@tagged('post_install', '-at_install')
class TestMerchantStoreOpenapi(TransactionCase):
    def test_openapi_json_matches_generator(self):
        """Committed ``docs/openapi.json`` must match running ``export_openapi``."""
        mod = _load_export_openapi()
        generated = mod.build_spec(mod.load_merchant_store_schemas())
        committed_path = Path(__file__).resolve().parents[1] / 'docs' / 'openapi.json'
        committed = json.loads(committed_path.read_text(encoding='utf-8'))
        self.assertEqual(
            generated,
            committed,
            'Run: python3 own_modules/merchant_store/scripts/export_openapi.py',
        )
        static_path = Path(__file__).resolve().parents[1] / 'static' / 'openapi.json'
        self.assertTrue(static_path.is_file(), 'Run export_openapi.py to create static/openapi.json')
        self.assertEqual(
            committed_path.read_text(encoding='utf-8'),
            static_path.read_text(encoding='utf-8'),
            'docs/openapi.json and static/openapi.json must stay in sync',
        )
