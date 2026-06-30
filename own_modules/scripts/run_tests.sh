#!/usr/bin/env bash
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Ejecuta los tests de los addons en own_modules/ vía `odoo-bin shell` + run_tests().
# Pensado para usarse con el servidor de desarrollo ya en marcha (puerto 8069):
# no hace -u ni arranca otro servidor en 8069; el harness de tests usa otro puerto.
#
# Uso:
#   ./own_modules/scripts/run_tests.sh
#   ./own_modules/scripts/run_tests.sh mcp_api
#   ./own_modules/scripts/run_tests.sh order_bridge listener
#   ./own_modules/scripts/run_tests.sh --tags /order_bridge:TestOrderBridgeStoreState
#   ./own_modules/scripts/run_tests.sh order_bridge listener --verbose
#
# Atajos order_bridge (tras el nombre del módulo, o solos con todos los módulos):
#   all       — todos los tests de order_bridge (por defecto para ese módulo)
#   listener  — TestOrderBridgeOrderCreatedListener
#   store     — TestOrderBridgeStoreState
#   api       — TestOrderBridgeApi (HttpCase; HTTP en el puerto del harness, no en 8069)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OWN_MODULES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DB="${ODOO_DB:-odoo}"
HTTP_PORT="${ODOO_TEST_HTTP_PORT:-8070}"
VERBOSE=0
EXTRA_ARGS=()
LOGFILE=""
TEST_TAGS=""
MODULES=()
ORDER_BRIDGE_SHORTCUTS=(all listener store api)

discover_test_modules() {
    local name dir
    for dir in "${OWN_MODULES_DIR}"/*/; do
        [[ -d "${dir}" ]] || continue
        name=$(basename "${dir}")
        [[ -f "${dir}__manifest__.py" && -d "${dir}tests" ]] && echo "${name}"
    done | sort
}

is_test_module() {
    local candidate="$1"
    local module
    while IFS= read -r module; do
        [[ "${module}" == "${candidate}" ]] && return 0
    done < <(discover_test_modules)
    return 1
}

is_order_bridge_shortcut() {
    local shortcut
    for shortcut in "${ORDER_BRIDGE_SHORTCUTS[@]}"; do
        [[ "${shortcut}" == "$1" ]] && return 0
    done
    return 1
}

resolve_order_bridge_shortcut() {
    case "${1:-all}" in
        all) TEST_TAGS="order_bridge" ;;
        listener) TEST_TAGS="/order_bridge:TestOrderBridgeOrderCreatedListener" ;;
        store) TEST_TAGS="/order_bridge:TestOrderBridgeStoreState" ;;
        api) TEST_TAGS="/order_bridge:TestOrderBridgeApi" ;;
        *)
            echo "Atajo order_bridge desconocido: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
}

join_by_comma() {
    local IFS=','
    echo "$*"
}

modules_to_python_list() {
    local module
    local parts=()
    for module in "$@"; do
        parts+=("'${module}'")
    done
    local IFS=', '
    echo "[${parts[*]}]"
}

usage() {
    cat <<EOF
Uso: run_tests.sh [modulo...] [atajo_order_bridge] [opciones]

Descubre automáticamente addons en own_modules/ con carpeta tests/ y __manifest__.py.
Sin módulos explícitos, ejecuta los tests de todos los descubiertos.

Asume que el servidor de desarrollo ya está corriendo (p. ej. en el puerto 8069).
Los tests se lanzan en un proceso aparte con \`odoo-bin shell\` para no mezclar
logs ni competir por el puerto del servidor.

Por defecto solo imprime un resumen en consola; los logs de Odoo van a un fichero
temporal (se muestra la ruta si hay fallos). Usa --verbose para ver todo en pantalla.

Módulos descubiertos:
$(discover_test_modules | sed 's/^/  /')

Atajos order_bridge (solo aplican a order_bridge):
  all        Todos los tests de order_bridge (por defecto para ese módulo)
  listener   test_order_bridge_order_created_listener
  store      test_order_bridge_store_state
  api        test_order_bridge_api (HttpCase)

Opciones:
  --list              Lista módulos descubiertos y sale
  --db NOMBRE         Base de datos (por defecto: odoo o \$ODOO_DB)
  --tags EXPRESION    --test-tags de Odoo (por defecto: nombres de módulos seleccionados)
  --http-port PUERTO  Puerto HTTP del harness de tests (por defecto: 8070 o \$ODOO_TEST_HTTP_PORT)
  --verbose           Muestra todos los logs de Odoo en consola
  -h, --help          Muestra esta ayuda

Variables de entorno:
  ODOO_DB              Base de datos
  ODOO_TEST_HTTP_PORT  Puerto HTTP solo para el harness de tests (no el servidor dev)
  ODOO_ADDONS_PATH     Rutas de addons (coma-separadas)

Notas:
  - No ejecuta \`-u\`. Tras cambios de código/schema, actualiza el módulo en el
    servidor en marcha (Apps o reinicio con -u) antes de correr los tests.
  - Los tests HTTP usan el harness en --http-port (8070), no el servidor en 8069.
  - Un atajo order_bridge sin prefijo de módulo filtra por tag pero carga todos los
    módulos descubiertos (útil solo para listener/store/api de order_bridge).

Ejemplos:
  ./own_modules/scripts/run_tests.sh
  ./own_modules/scripts/run_tests.sh mcp_api
  ./own_modules/scripts/run_tests.sh order_bridge mcp_api
  ./own_modules/scripts/run_tests.sh order_bridge listener
  ./own_modules/scripts/run_tests.sh --tags '/order_bridge:TestOrderBridgeOrderCreatedListener'
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --list)
            discover_test_modules
            exit 0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --db|--tags|--http-port)
            break
            ;;
        --verbose|--no-update)
            break
            ;;
        --*)
            break
            ;;
        *)
            if is_test_module "$1"; then
                MODULES+=("$1")
                shift
                if [[ $# -gt 0 && "${1:0:2}" != "--" ]] && is_order_bridge_shortcut "$1"; then
                    resolve_order_bridge_shortcut "$1"
                    shift
                fi
                continue
            fi
            if is_order_bridge_shortcut "$1"; then
                resolve_order_bridge_shortcut "$1"
                shift
                continue
            fi
            echo "Argumento desconocido: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db)
            DB="$2"
            shift 2
            ;;
        --tags)
            TEST_TAGS="$2"
            shift 2
            ;;
        --http-port)
            HTTP_PORT="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        --no-update)
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#MODULES[@]} -eq 0 ]]; then
    mapfile -t MODULES < <(discover_test_modules)
fi

if [[ ${#MODULES[@]} -eq 0 ]]; then
    echo "No se encontraron módulos con tests en ${OWN_MODULES_DIR}" >&2
    exit 1
fi

if [[ -z "${TEST_TAGS}" ]]; then
    TEST_TAGS="$(join_by_comma "${MODULES[@]}")"
fi

PYTHON_MODULES="$(modules_to_python_list "${MODULES[@]}")"
MODULES_LABEL="$(join_by_comma "${MODULES[@]}")"

ADDONS_PATH="${ODOO_ADDONS_PATH:-${REPO_ROOT}/odoo/addons,${REPO_ROOT}/addons,${REPO_ROOT}/own_modules,${REPO_ROOT}/oca}"

LOG_ARGS=()
if [[ "${VERBOSE}" -eq 0 ]]; then
    LOGFILE="$(mktemp "${TMPDIR:-/tmp}/own_modules_tests.XXXXXX.log")"
    LOG_ARGS=(--logfile "${LOGFILE}")
fi

echo "==> own_modules tests (${MODULES_LABEL})"
echo "    db:         ${DB}"
echo "    test-tags:  ${TEST_TAGS}"
echo "    http-port:  ${HTTP_PORT}"
echo "    output:     $([[ "${VERBOSE}" -eq 1 ]] && echo verbose || echo summary)"
echo

cd "${REPO_ROOT}"

set +e
if [[ "${VERBOSE}" -eq 1 ]]; then
    python3 "${REPO_ROOT}/odoo-bin" shell \
        -d "${DB}" \
        --http-port "${HTTP_PORT}" \
        --addons-path "${ADDONS_PATH}" \
        "${EXTRA_ARGS[@]}" <<PY
from odoo.tests.shell import run_tests

report = run_tests(env, ${TEST_TAGS@Q}, modules=${PYTHON_MODULES})
raise SystemExit(0 if report.wasSuccessful() else 1)
PY
else
    python3 "${REPO_ROOT}/odoo-bin" shell \
        -d "${DB}" \
        --http-port "${HTTP_PORT}" \
        --addons-path "${ADDONS_PATH}" \
        "${LOG_ARGS[@]}" \
        "${EXTRA_ARGS[@]}" <<PY
import re

from odoo.tests.shell import run_tests

report = run_tests(env, ${TEST_TAGS@Q}, modules=${PYTHON_MODULES})
passed = report.testsRun - report.failures_count - report.errors_count
print(f"passed:  {passed}")
print(f"failed:  {report.failures_count}")
print(f"errors:  {report.errors_count}")
print(f"total:   {report.testsRun}")

if not report.wasSuccessful():
    logfile = ${LOGFILE@Q}
    if logfile:
        print()
        print("--- failures ---")
        with open(logfile, encoding="utf-8") as handle:
            lines = handle.readlines()
        in_block = False
        for line in lines:
            if re.search(r"\\b(FAIL|ERROR):", line):
                in_block = True
            if in_block:
                cleaned = re.sub(r"^\\d{4}-\\d{2}-\\d{2} .*? (?:ERROR|INFO|WARNING) odoo [^:]+: ", "", line.rstrip())
                print(cleaned)
                if not line.strip():
                    in_block = False
        print()
        print(f"log: {logfile}")

raise SystemExit(0 if report.wasSuccessful() else 1)
PY
fi
EXIT_CODE=$?
set -e

if [[ "${EXIT_CODE}" -eq 0 && -n "${LOGFILE}" ]]; then
    rm -f "${LOGFILE}"
fi

exit "${EXIT_CODE}"
