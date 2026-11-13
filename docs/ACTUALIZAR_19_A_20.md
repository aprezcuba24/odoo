# Actualizar 19.0 y pasar el proyecto a 20.0

La rama de trabajo es **`update-app`**, no `dev`. `dev` se deja como está.

El cambio de código no migra la base de datos. El fetch git de 20.0 no se puede reanudar (GitHub corta el pack de ~3.6 millones de objetos). Se baja el snapshot con `curl -C -` y se arma la rama 20.0 encima, copiando los addons de `update-app`.

## Progreso

- Hecho: fetch upstream y fast-forward de la rama 19.0
- Hecho: merge de 19.0 en `update-app` (`29b9203abc7`)
- Pendiente: bajar el tar.gz de 20.0 con `curl -C -` (reanudable), crear la rama huérfana 20.0 y copiar `own_modules`, `oca`, deploy y el parche de `server.py` desde `update-app`
- Pendiente: subir versiones de manifests propios a 20.0 y revisar módulos OCA

## Estado

- `upstream` = `https://github.com/odoo/odoo.git` (fetch limitado a `19.0`)
- `origin` = `aprezcuba24/odoo`
- Rama actual: `update-app` en `29b9203abc7` (`Merge branch '19.0' into update-app`)
- `19.0` local ya está en `74d39b2fdaa` y es el segundo padre de ese merge
- `upstream/20.0` existe en GitHub (`0ecb5316b2e`) pero no en el clon, porque el fetch de `upstream` solo pide `refs/heads/19.0`

El núcleo propio casi no se tocó: el único cambio en `odoo/` es comentar `check_postgres_user()` en [`odoo/cli/server.py`](../odoo/cli/server.py). El resto es `own_modules/`, `oca/`, Docker, docs y `.gitignore`.

No hagas `git merge update-app` encima de `upstream/20.0`. Eso fusiona todo el historial del core 19 con el 20. Se copian las carpetas propias de `update-app` encima de un 20.0 limpio.

## 1. 19.0 de upstream (hecho)

`19.0` local ya avanzó a `upstream/19.0` y está fusionada en `update-app`. No hace falta repetir el merge.

## 2. Bajar 20.0 y poner encima lo de `update-app`

No reintentes `git fetch upstream 20.0:...`. GitHub manda el historial entero (3.6 millones de objetos, varios GiB). La conexión se corta (`curl 56`, `early EOF`) y Git tira el pack a medias: no hay resume, por eso cada intento vuelve a enumerar y a bajar desde cero.

`git fetch --depth=1` dentro de este clon lo marcaría como shallow y estropea `19.0` y `update-app`. El snapshot de GitHub sí se reanuda.

```bash
curl -L -C - --retry 30 --retry-all-errors \
  -o "$HOME/odoo-20.0.tar.gz" \
  https://codeload.github.com/odoo/odoo/tar.gz/refs/heads/20.0
```

Si se corta, ejecuta el mismo comando. `-C -` sigue desde el byte donde quedó el archivo. Cuando termine:

```bash
mkdir -p "$HOME/odoo-20-src"
tar -xzf "$HOME/odoo-20.0.tar.gz" -C "$HOME/odoo-20-src"
# queda en $HOME/odoo-20-src/odoo-20.0/

cd /home/renier/Development/DESARROLLO/ODOO/odoo
git switch --orphan 20.0
rsync -a --delete --exclude '.git' "$HOME/odoo-20-src/odoo-20.0/" ./
git add -A
git commit -m "Import Odoo 20.0 tree from upstream snapshot"

git checkout update-app -- \
  own_modules \
  oca \
  extensions \
  docs \
  scripts \
  .devcontainer \
  .github \
  .agents \
  .claude \
  Dockerfile \
  docker-entrypoint.sh \
  odoo-wsgi.py \
  gunicorn.conf.py \
  gunicorn_gevent_handler.py \
  build.sh \
  dev-https-setup.sh \
  requirements.txt \
  CLAUDE.md \
  SEENODE_DEPLOYMENT.md \
  README.md \
  .gitignore
```

Reaplicar a mano el parche de Railway en `odoo/cli/server.py` de la 20.0 (la línea puede haberse movido): dejar comentada la llamada a `check_postgres_user()`.

Odoo 20 rechaza módulos cuya versión no empiece por `20.0`. Hoy están en serie 19:

- [`own_modules/order_bridge/__manifest__.py`](../own_modules/order_bridge/__manifest__.py) `19.0.1.6.0`
- [`own_modules/company_onboarding/__manifest__.py`](../own_modules/company_onboarding/__manifest__.py) `19.0.1.3.0`
- [`own_modules/bi_analytics/__manifest__.py`](../own_modules/bi_analytics/__manifest__.py) `19.0.1.0.0`
- [`own_modules/mcp_api/__manifest__.py`](../own_modules/mcp_api/__manifest__.py) `19.0.1.0.0`
- `oca/fs_attachment`, `oca/fs_storage`, `oca/server_environment` también en `19.0.*`

Para los propios, subir el prefijo a `20.0` (la carpeta `migrations/19.0.*` no se reejecuta; hace falta una migración `20.0.*` si el esquema cambia). Para OCA, mejor sustituir esas tres carpetas por la rama 20.0 de OCA cuando exista, en lugar de solo cambiar el string de versión.

```bash
git add -A
git status
git commit -m "Start 20.0 from upstream and carry custom addons"
```

Publicar la rama solo cuando la revises:

```bash
git push -u origin 20.0
```

Esa rama `20.0` es huérfana: tiene el árbol de archivos de upstream, no su historial. Un `git pull` posterior no hará fast-forward. `update-app` no se toca. El `rsync` va después de `git switch --orphan 20.0`; si lo lanzas todavía en `update-app`, vacía el directorio de trabajo de esa rama (el commit queda intacto, pero es evitable).

## Lo que estos comandos no hacen

Cambiar el código a 20.0 no migra PostgreSQL. `-u all` solo actualiza módulos dentro de la misma serie. Una base 19 contra código 20 no arranca bien. La vía community es [OCA/OpenUpgrade](https://github.com/OCA/OpenUpgrade) (si ya tiene scripts 19→20); si no, hay que esperar o usar el servicio de upgrade de Odoo. Haz esa prueba en una copia de la base, no en producción.
