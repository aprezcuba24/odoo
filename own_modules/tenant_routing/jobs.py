# Part of this repository. License: LGPL-3.
"""Provision jobs with log streaming (file-backed so any Gunicorn worker can stream)."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

_logger = logging.getLogger(__name__)

TENANT_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
JOB_DIR = Path(os.environ.get('TENANT_PROVISION_JOB_DIR', '/tmp/tenant_provision_jobs'))
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / 'scripts' / 'provision_tenant.sh'


def multi_tenant_enabled() -> bool:
    return os.environ.get('ODOO_MULTI_TENANT', '').strip().lower() in (
        '1',
        'true',
        'yes',
        'on',
    )


def _job_paths(job_id: str) -> tuple[Path, Path]:
    base = JOB_DIR / job_id
    return base.with_suffix('.meta.json'), base.with_suffix('.log')


def _write_meta(job_id: str, **fields) -> None:
    meta_path, _ = _job_paths(job_id)
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if meta_path.is_file():
        try:
            data = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            data = {}
    data.update(fields)
    meta_path.write_text(json.dumps(data), encoding='utf-8')


def get_job(job_id: str) -> dict | None:
    meta_path, log_path = _job_paths(job_id)
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    meta['log_path'] = str(log_path)
    return meta


def start_provision_job(
    *,
    tenant: str,
    extra_modules: str = '',
    force_recreate: bool = False,
) -> str:
    if not TENANT_NAME_RE.match(tenant):
        raise ValueError(
            'Nombre de tenant inválido (letras, números y _; debe empezar por letra).'
        )
    if not SCRIPT_PATH.is_file():
        raise FileNotFoundError(f'No se encuentra {SCRIPT_PATH}')

    job_id = uuid.uuid4().hex
    meta_path, log_path = _job_paths(job_id)
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    log_path.write_text('', encoding='utf-8')
    _write_meta(
        job_id,
        id=job_id,
        tenant=tenant,
        done=False,
        returncode=None,
        error=None,
        started_at=time.time(),
        finished_at=None,
    )

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, tenant, extra_modules, force_recreate),
        name=f'provision-{tenant}',
        daemon=True,
    )
    thread.start()
    return job_id


def _append(job_id: str, line: str) -> None:
    _, log_path = _job_paths(job_id)
    with log_path.open('a', encoding='utf-8') as fh:
        fh.write(line.rstrip('\n') + '\n')


def _run_job(job_id: str, tenant: str, extra_modules: str, force_recreate: bool) -> None:
    env = os.environ.copy()
    if force_recreate:
        env['PROVISION_FORCE_RECREATE'] = 'true'
    if not env.get('ODOO_ADDONS_PATH'):
        env['ODOO_ADDONS_PATH'] = ','.join(
            str(REPO_ROOT / p)
            for p in ('odoo/addons', 'addons', 'own_modules', 'oca')
        )

    cmd = ['bash', str(SCRIPT_PATH), tenant]
    if extra_modules.strip():
        cmd.append(extra_modules.strip())

    _append(job_id, f'[web] Iniciando: {" ".join(cmd)}')
    _logger.info('tenant_routing provision job %s: %s', job_id, cmd)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            _append(job_id, line)
        code = proc.wait()
        if code == 0:
            _append(job_id, f'[web] Completado OK (exit {code}).')
        else:
            _append(job_id, f'[web] Falló con código {code}.')
        _write_meta(job_id, done=True, returncode=code, finished_at=time.time())
    except Exception as e:
        _append(job_id, f'[web] ERROR: {e}')
        _logger.exception('tenant_routing provision job %s failed', job_id)
        _write_meta(
            job_id,
            done=True,
            returncode=1,
            error=str(e),
            finished_at=time.time(),
        )


def read_log_lines(job_id: str, from_index: int = 0) -> tuple[list[str], int, bool, int | None]:
    job = get_job(job_id)
    if not job:
        return [], 0, True, 1
    _, log_path = _job_paths(job_id)
    lines: list[str] = []
    if log_path.is_file():
        lines = log_path.read_text(encoding='utf-8').splitlines()
    return lines[from_index:], len(lines), bool(job.get('done')), job.get('returncode')
