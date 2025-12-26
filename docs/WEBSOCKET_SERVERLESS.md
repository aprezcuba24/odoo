# Websockets en Entornos Serverless

## Problema

Los websockets requieren conexiones TCP persistentes que se mantienen abiertas. Los entornos serverless típicamente:

1. **Tienen timeouts cortos** (30-60 segundos) que cierran conexiones idle
2. **No mantienen estado** entre requests
3. **Usan proxies HTTP** que pueden cerrar conexiones persistentes
4. **Escalan a cero** cuando no hay tráfico, matando conexiones activas

## Soluciones

### 1. Verificar si tu plataforma soporta websockets

#### ✅ Plataformas que SÍ soportan websockets:
- **Railway** - Soporta websockets, pero puede necesitar configuración
- **Render** - Soporta websockets con configuración adecuada
- **DigitalOcean App Platform** - Soporta websockets
- **Fly.io** - Soporta websockets
- **Heroku** - Soporta websockets
- **Google Cloud Run** - Soporta websockets (con configuración)
- **AWS ECS/Fargate** - Soporta websockets
- **Kubernetes** - Soporta websockets

#### ❌ Plataformas que NO soportan websockets:
- **AWS Lambda** - No soporta conexiones persistentes
- **Vercel** - No soporta websockets (solo serverless functions)
- **Netlify Functions** - No soporta websockets
- **Cloudflare Workers** - Limitado, no soporta websockets tradicionales

### 2. Configuración para Railway

Si estás usando Railway, asegúrate de:

1. **No usar modo "serverless"**: Railway tiene un modo serverless que no soporta websockets
2. **Usar servicios persistentes**: Asegúrate de que el servicio esté configurado como "Always On"
3. **Configurar timeouts largos**: Railway puede tener timeouts, configúralos apropiadamente

### 3. Configuración de timeouts

Añade estas variables de entorno en tu plataforma:

```bash
# Timeouts largos para websockets
GUNICORN_TIMEOUT=600  # 10 minutos
GUNICORN_KEEPALIVE=75  # Mantener conexiones vivas
```

### 4. Fallback a Polling (si no hay websockets)

Si tu plataforma no soporta websockets, Odoo puede usar polling como fallback. Esto se configura automáticamente, pero puedes forzarlo deshabilitando websockets.

### 5. Verificar la configuración

Para verificar si el problema es el entorno serverless:

1. **Revisa los logs**: Busca errores de timeout o "connection closed"
2. **Verifica el tiempo de vida de las conexiones**: Si se cierran después de ~30-60 segundos, es un timeout del proxy
3. **Prueba localmente**: Si funciona localmente pero no en producción, confirma que es el entorno

## Configuración Recomendada

### Para Railway:

```yaml
# railway.json o configuración del servicio
{
  "deploy": {
    "startCommand": "gunicorn odoo-wsgi:application --pythonpath /app --config /app/gunicorn.conf.py",
    "healthcheckPath": "/web/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Variables de entorno recomendadas:

```bash
# Gunicorn - timeouts largos para websockets
GUNICORN_TIMEOUT=600
GUNICORN_KEEPALIVE=75
GUNICORN_WORKER_CLASS=gevent
GUNICORN_WORKER_CONNECTIONS=1000

# Asegurar que el servicio no se duerma
# (depende de la plataforma)
```

## Alternativas si no puedes usar websockets

Si tu plataforma no soporta websockets:

1. **Usar polling**: Odoo automáticamente usará polling si los websockets fallan
2. **Migrar a una plataforma que soporte websockets**: Railway, Render, Fly.io, etc.
3. **Usar un servicio proxy**: Coloca un proxy (nginx, Caddy) delante que maneje websockets

## Diagnóstico

Para diagnosticar si el problema es serverless:

```bash
# Verificar si las conexiones se cierran por timeout
# Revisa los logs para ver el tiempo entre conexión y desconexión

# Si ves patrones como:
# - Conexiones que se cierran después de 30-60 segundos
# - Errores de "connection reset" o "timeout"
# - El websocket se conecta pero se cae inmediatamente

# Entonces es muy probable que sea un problema del entorno serverless
```

