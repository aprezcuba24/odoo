#!/usr/bin/env python3
"""Prueba rápida de carga de .env en local.

1. Añade en .env (o cambia el valor y guarda):

       LOCAL_DOTENV_TEST=hola-mundo

2. Ejecuta:

       python3 scripts/check_local_dotenv.py

3. Cambia el valor en .env (p. ej. LOCAL_DOTENV_TEST=otro-valor) y vuelve a ejecutar.
   Deberías ver el valor nuevo sin recrear el contenedor.

Opcional: pasa otra variable como argumento:

       python3 scripts/check_local_dotenv.py DB_LANGUAGE
"""

from __future__ import annotations

import importlib.util
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DOTENV_PATH = os.path.join(
    _REPO_ROOT,
    "own_modules",
    "order_bridge",
    "utils",
    "local_dotenv.py",
)

_spec = importlib.util.spec_from_file_location("local_dotenv", _DOTENV_PATH)
_local_dotenv = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_local_dotenv)
load_local_dotenv = _local_dotenv.load_local_dotenv


def main() -> int:
    var_name = (sys.argv[1] if len(sys.argv) > 1 else "LOCAL_DOTENV_TEST").strip()
    before = os.environ.get(var_name, "<no definida>")

    loaded = load_local_dotenv()
    after = os.environ.get(var_name, "<no definida>")

    print(f"Variable: {var_name}")
    print(f"Antes de load_local_dotenv(): {before!r}")
    print(f"Después de load_local_dotenv(): {after!r}")
    print(f"Claves cargadas desde .env: {loaded}")

    if after == "<no definida>":
        print()
        print(f"Añade en .env: {var_name}=tu-valor-de-prueba")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
