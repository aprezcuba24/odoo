# Configuración de Gunicorn para Odoo en Producción

Este documento describe cómo configurar y ejecutar Odoo con Gunicorn en un entorno de producción.

## Archivos Creados

1. **`odoo-wsgi.py`** - Archivo de configuración WSGI para Gunicorn
2. **`gunicorn.conf.py`** - Archivo de configuración de Gunicorn
3. **`odoo-gunicorn.service`** - Archivo de servicio systemd
4. **`start-gunicorn.sh`** - Script de inicio manual
5. **`requirements.txt`** - Actualizado con Gunicorn

## Requisitos Previos

- Python 3.10 o superior
- PostgreSQL instalado y configurado
- Usuario dedicado para Odoo (recomendado: `odoo`)
- Directorios de logs y runtime creados

## Instalación

### 1. Instalar Dependencias

```bash
# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configurar Directorios

```bash
# Crear directorios necesarios
sudo mkdir -p /var/log/odoo /var/run/odoo
sudo chown -R odoo:odoo /var/log/odoo /var/run/odoo
```

### 3. Configurar Odoo

Edita `odoo-wsgi.py` y ajusta las siguientes configuraciones según tu entorno:

```python
# Ruta de addons
conf['addons_path'] = './odoo/addons,./addons'

# Configuración de base de datos
conf['db_name'] = 'odoo'
conf['db_host'] = 'localhost'
conf['db_user'] = 'odoo'
conf['db_port'] = 5432
conf['db_password'] = 'tu_contraseña'
```

## Uso

### Opción 1: Usando el Script de Inicio

```bash
./start-gunicorn.sh
```

### Opción 2: Usando Gunicorn Directamente

```bash
# Con archivo de configuración WSGI
gunicorn odoo.http:root --pythonpath . -c odoo-wsgi.py

# O con archivo de configuración separado
gunicorn odoo.http:root --pythonpath . -c gunicorn.conf.py
```

### Opción 3: Usando Systemd (Recomendado para Producción)

1. **Copiar el archivo de servicio:**

```bash
sudo cp odoo-gunicorn.service /etc/systemd/system/
```

2. **Editar el servicio** (ajustar rutas y usuario):

```bash
sudo nano /etc/systemd/system/odoo-gunicorn.service
```

Ajusta las siguientes líneas según tu entorno:
- `User=odoo` - Usuario que ejecutará Odoo
- `Group=odoo` - Grupo del usuario
- `WorkingDirectory=/app` - Directorio del proyecto
- `ExecStart=/usr/bin/gunicorn` - Ruta al ejecutable de Gunicorn (ajusta según tu instalación)

3. **Recargar systemd y habilitar el servicio:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable odoo-gunicorn
sudo systemctl start odoo-gunicorn
```

4. **Verificar el estado:**

```bash
sudo systemctl status odoo-gunicorn
```

5. **Ver logs:**

```bash
sudo journalctl -u odoo-gunicorn -f
```

## Configuración de Gunicorn

### Variables de Entorno

Puedes configurar Gunicorn usando variables de entorno:

```bash
export GUNICORN_BIND="0.0.0.0:8069"
export GUNICORN_WORKERS="8"
export GUNICORN_TIMEOUT="300"
export GUNICORN_MAX_REQUESTS="5000"
export GUNICORN_ACCESS_LOG="/var/log/odoo/gunicorn-access.log"
export GUNICORN_ERROR_LOG="/var/log/odoo/gunicorn-error.log"
export GUNICORN_LOG_LEVEL="info"
export GUNICORN_PIDFILE="/var/run/odoo/gunicorn.pid"
```

### Ajuste de Workers

La fórmula recomendada para el número de workers es:
```
workers = (2 × CPU cores) + 1
```

Por ejemplo, para un servidor con 4 cores:
```python
workers = 9
```

### Configuración de Timeout

Odoo puede tener operaciones largas, por lo que se recomienda un timeout de al menos 240 segundos. Ajusta según tus necesidades.

## Configuración con Nginx (Recomendado)

Para usar Nginx como proxy reverso, configura un archivo como este:

```nginx
upstream odoo {
    server 127.0.0.1:8069;
}

server {
    listen 80;
    server_name tu-dominio.com;

    # Logs
    access_log /var/log/nginx/odoo-access.log;
    error_log /var/log/nginx/odoo-error.log;

    # Increase proxy buffer size
    proxy_buffers 16 64k;
    proxy_buffer_size 128k;

    # Timeouts
    proxy_read_timeout 240s;
    proxy_connect_timeout 240s;
    proxy_send_timeout 240s;

    location / {
        proxy_pass http://odoo;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_redirect off;
    }

    # Cache static files
    location ~* /web/static/ {
        proxy_cache_valid 200 60m;
        proxy_buffering on;
        expires 864000;
        proxy_pass http://odoo;
    }
}
```

## Monitoreo y Mantenimiento

### Verificar Procesos

```bash
ps aux | grep gunicorn
```

### Reiniciar el Servicio

```bash
# Con systemd
sudo systemctl restart odoo-gunicorn

# O enviando señal HUP al proceso maestro
kill -HUP $(cat /var/run/odoo/gunicorn.pid)
```

### Detener el Servicio

```bash
# Con systemd
sudo systemctl stop odoo-gunicorn

# O enviando señal TERM al proceso maestro
kill -TERM $(cat /var/run/odoo/gunicorn.pid)
```

### Ver Logs

```bash
# Logs de systemd
sudo journalctl -u odoo-gunicorn -f

# Logs de Gunicorn
tail -f /var/log/odoo/gunicorn-access.log
tail -f /var/log/odoo/gunicorn-error.log
```

## Solución de Problemas

### Error: "Address already in use"

El puerto 8069 está en uso. Verifica qué proceso lo está usando:

```bash
sudo lsof -i :8069
```

### Error: "Permission denied"

Asegúrate de que los directorios de logs y runtime tengan los permisos correctos:

```bash
sudo chown -R odoo:odoo /var/log/odoo /var/run/odoo
```

### Workers no responden

Aumenta el timeout en la configuración:

```python
timeout = 300  # o más
```

### Problemas de memoria

Reduce el número de workers o ajusta `max_requests`:

```python
workers = 4
max_requests = 1000
```

## Seguridad

1. **Ejecutar como usuario no root**: El servicio systemd está configurado para ejecutarse como usuario `odoo`.

2. **Firewall**: Asegúrate de que solo Nginx pueda acceder al puerto 8069:

```bash
sudo ufw allow from 127.0.0.1 to any port 8069
```

3. **HTTPS**: Configura SSL/TLS en Nginx, no en Gunicorn directamente.

4. **Logs**: Revisa regularmente los logs para detectar problemas de seguridad.

## Recursos Adicionales

- [Documentación de Gunicorn](https://docs.gunicorn.org/)
- [Documentación de Odoo](https://www.odoo.com/documentation/)
- [Guía de Despliegue de Odoo](https://www.odoo.com/documentation/master/administration/install/deploy.html)

