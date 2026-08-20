# Part of Odoo. See LICENSE file for full copyright and licensing details.

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from odoo.tests.common import BaseCase, tagged

from odoo.addons.order_bridge.utils import local_dotenv


@tagged("post_install", "-at_install")
class TestLocalDotenv(BaseCase):
    def test_missing_file_is_noop(self):
        with patch.dict(os.environ, {}, clear=True):
            count = local_dotenv.load_local_dotenv(
                env_path=Path("/nonexistent/.env"),
            )
        self.assertEqual(count, 0)

    def test_skips_on_railway(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
            tmp.write("FOO=bar\n")
            tmp_path = Path(tmp.name)
        try:
            with patch.dict(
                os.environ,
                {"RAILWAY_ENVIRONMENT": "production"},
                clear=True,
            ):
                count = local_dotenv.load_local_dotenv(env_path=tmp_path)
            self.assertEqual(count, 0)
            self.assertNotIn("FOO", os.environ)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_parses_comments_quotes_and_export(self):
        content = "\n".join(
            [
                "# comment",
                "",
                "export PLAIN=value",
                'QUOTED="hello\\nworld"',
                "SINGLE='literal\\n'",
                'JSON={"type": "service_account"}',
            ]
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            with patch.dict(os.environ, {}, clear=True):
                count = local_dotenv.load_local_dotenv(env_path=tmp_path)
                self.assertEqual(count, 4)
                self.assertEqual(os.environ["PLAIN"], "value")
                self.assertEqual(os.environ["QUOTED"], "hello\nworld")
                self.assertEqual(os.environ["SINGLE"], "literal\\n")
                self.assertEqual(os.environ["JSON"], '{"type": "service_account"}')
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_does_not_override_compose_protected_keys(self):
        content = "\n".join(
            [
                "PGHOST=remote-host",
                "ORDER_BRIDGE_FCM_TOKEN=from-env-file",
            ]
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            with patch.dict(
                os.environ,
                {"PGHOST": "postgres"},
                clear=True,
            ):
                count = local_dotenv.load_local_dotenv(env_path=tmp_path)
                self.assertEqual(count, 1)
                self.assertEqual(os.environ["PGHOST"], "postgres")
                self.assertEqual(
                    os.environ["ORDER_BRIDGE_FCM_TOKEN"],
                    "from-env-file",
                )
        finally:
            tmp_path.unlink(missing_ok=True)
