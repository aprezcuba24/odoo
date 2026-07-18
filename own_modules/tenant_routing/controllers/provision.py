# Part of this repository. License: LGPL-3.

from __future__ import annotations

import json
import logging
import time

from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request, Response
from odoo.service import db as db_service

from odoo.addons.tenant_routing import jobs

_logger = logging.getLogger(__name__)

PAGE_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Provisionar tenant</title>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9bb4;
      --accent: #3d8bfd;
      --ok: #3dd68c;
      --err: #f07178;
      --border: #2a3548;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: ui-sans-serif, system-ui, sans-serif;
      background: var(--bg); color: var(--text); min-height: 100vh;
      padding: 1.5rem;
    }
    main { max-width: 920px; margin: 0 auto; }
    h1 { font-size: 1.35rem; margin: 0 0 0.35rem; }
    p.lead { color: var(--muted); margin: 0 0 1.25rem; font-size: 0.95rem; }
    .panel {
      background: var(--panel); border: 1px solid var(--border);
      border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem;
    }
    label { display: block; font-size: 0.8rem; color: var(--muted); margin-bottom: 0.25rem; }
    input[type=text], input[type=password] {
      width: 100%; padding: 0.55rem 0.7rem; border-radius: 6px;
      border: 1px solid var(--border); background: #0d121a; color: var(--text);
      margin-bottom: 0.85rem; font-size: 0.95rem;
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
    @media (max-width: 640px) { .row { grid-template-columns: 1fr; } }
    .check { display: flex; align-items: center; gap: 0.5rem; margin: 0.5rem 0 1rem; color: var(--muted); font-size: 0.9rem; }
    button {
      background: var(--accent); color: #fff; border: 0; border-radius: 6px;
      padding: 0.65rem 1.1rem; font-weight: 600; cursor: pointer; font-size: 0.95rem;
    }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    #status { margin-left: 0.75rem; font-size: 0.9rem; color: var(--muted); }
    #status.ok { color: var(--ok); }
    #status.err { color: var(--err); }
    #log {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.78rem; line-height: 1.45; white-space: pre-wrap; word-break: break-word;
      background: #0a0e14; border: 1px solid var(--border); border-radius: 8px;
      padding: 0.85rem; height: min(55vh, 480px); overflow: auto; margin: 0;
    }
    .hint { font-size: 0.8rem; color: var(--muted); margin-top: 0.75rem; }
  </style>
</head>
<body>
  <main>
    <h1>Provisionar tenant</h1>
    <p class="lead">Crea o repara una base de datos Odoo en este servidor (idempotente). Requiere la contraseña maestra (<code>DB_PASSWORD_ADMIN</code>).</p>

    <div class="panel">
      <form id="form">
        <label for="master_pwd">Contraseña maestra</label>
        <input id="master_pwd" name="master_pwd" type="password" autocomplete="current-password" required/>

        <div class="row">
          <div>
            <label for="tenant">Nombre del tenant (BD)</label>
            <input id="tenant" name="tenant" type="text" pattern="[A-Za-z][A-Za-z0-9_]*" placeholder="demo" required/>
          </div>
          <div>
            <label for="modules">Módulos extra (opcional, coma-separados)</label>
            <input id="modules" name="modules" type="text" placeholder="order_bridge,fs_attachment"/>
          </div>
        </div>

        <label class="check">
          <input id="force" name="force" type="checkbox"/>
          Forzar recreación aunque la BD ya esté lista
        </label>

        <button type="submit" id="btn">Provisionar</button>
        <span id="status"></span>
      </form>
      <p class="hint">Tras terminar: añade el nombre a <code>ODOO_TENANT_DATABASES</code> y, si usas la URL de Railway, a <code>ODOO_TENANT_DOMAIN_MAP</code>.</p>
    </div>

    <div class="panel">
      <label>Logs</label>
      <pre id="log"></pre>
    </div>
  </main>
  <script>
    const form = document.getElementById('form');
    const logEl = document.getElementById('log');
    const statusEl = document.getElementById('status');
    const btn = document.getElementById('btn');
    let es = null;

    function appendLog(line) {
      logEl.textContent += line + '\\n';
      logEl.scrollTop = logEl.scrollHeight;
    }

    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (es) { es.close(); es = null; }
      logEl.textContent = '';
      statusEl.textContent = 'Iniciando…';
      statusEl.className = '';
      btn.disabled = true;

      const body = new URLSearchParams({
        master_pwd: document.getElementById('master_pwd').value,
        tenant: document.getElementById('tenant').value.trim(),
        modules: document.getElementById('modules').value.trim(),
        force: document.getElementById('force').checked ? '1' : '0',
      });

      let jobId;
      try {
        const res = await fetch('/tenant/provision/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        jobId = data.job_id;
      } catch (e) {
        statusEl.textContent = e.message || String(e);
        statusEl.className = 'err';
        btn.disabled = false;
        return;
      }

      statusEl.textContent = 'En curso…';
      es = new EventSource('/tenant/provision/stream/' + jobId);
      es.onmessage = (ev) => {
        try { appendLog(JSON.parse(ev.data)); }
        catch { appendLog(ev.data); }
      };
      es.addEventListener('done', (ev) => {
        const code = parseInt(ev.data, 10);
        if (code === 0) {
          statusEl.textContent = 'Completado';
          statusEl.className = 'ok';
        } else {
          statusEl.textContent = 'Falló (código ' + code + ')';
          statusEl.className = 'err';
        }
        es.close();
        es = null;
        btn.disabled = false;
      });
      es.addEventListener('error', () => {
        if (es && es.readyState === EventSource.CLOSED) return;
        statusEl.textContent = 'Conexión de logs interrumpida';
        statusEl.className = 'err';
        btn.disabled = false;
      });
    });
  </script>
</body>
</html>
"""


class TenantProvisionController(http.Controller):

    def _ensure_enabled(self):
        if not jobs.multi_tenant_enabled():
            return request.make_response(
                'Tenant provision UI requires ODOO_MULTI_TENANT=true.',
                status=403,
                headers=[('Content-Type', 'text/plain; charset=utf-8')],
            )
        return None

    @http.route('/tenant/provision', type='http', auth='none', methods=['GET'], csrf=False, save_session=False)
    def provision_page(self, **kw):
        denied = self._ensure_enabled()
        if denied:
            return denied
        if request.db:
            try:
                request.env.cr.close()
            except Exception:
                pass
        return Response(PAGE_HTML, headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route(
        '/tenant/provision/start',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def provision_start(self, master_pwd='', tenant='', modules='', force='0', **kw):
        if not jobs.multi_tenant_enabled():
            return request.make_json_response({'error': 'ODOO_MULTI_TENANT disabled'}, status=403)
        try:
            db_service.check_super(master_pwd)
        except AccessDenied:
            return request.make_json_response({'error': 'Contraseña maestra incorrecta'}, status=403)

        tenant = (tenant or '').strip()
        modules = (modules or '').strip()
        force_recreate = str(force).lower() in ('1', 'true', 'yes', 'on')

        try:
            job_id = jobs.start_provision_job(
                tenant=tenant,
                extra_modules=modules,
                force_recreate=force_recreate,
            )
        except Exception as e:
            _logger.exception('Failed to start provision job')
            return request.make_json_response({'error': str(e)}, status=400)

        return request.make_json_response({'job_id': job_id})

    @http.route(
        '/tenant/provision/stream/<string:job_id>',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def provision_stream(self, job_id, **kw):
        if not jobs.multi_tenant_enabled():
            return request.make_response('forbidden', status=403)

        def generate():
            idx = 0
            idle_rounds = 0
            while True:
                job = jobs.get_job(job_id)
                if not job:
                    yield f'event: done\ndata: 1\n\n'
                    return
                chunk, idx, done, code = jobs.read_log_lines(job_id, idx)
                for line in chunk:
                    yield f'data: {json.dumps(line, ensure_ascii=False)}\n\n'
                    idle_rounds = 0
                if done:
                    yield f'event: done\ndata: {0 if code == 0 else (code or 1)}\n\n'
                    return
                idle_rounds += 1
                # Keep-alive comment for proxies
                if idle_rounds % 10 == 0:
                    yield ': ping\n\n'
                time.sleep(0.4)

        headers = [
            ('Content-Type', 'text/event-stream; charset=utf-8'),
            ('Cache-Control', 'no-cache'),
            ('X-Accel-Buffering', 'no'),
        ]
        return Response(generate(), headers=headers)
