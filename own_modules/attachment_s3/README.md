# attachment_s3

Módulo reutilizable para guardar adjuntos binarios de `ir.attachment` en Amazon S3 (o compatible S3) cuando está activo.

## Qué hace

- Es global para toda la instancia.
- Solo actúa cuando:
  1. Está instalado.
  2. El interruptor **Use S3 for file attachments** está activo en Ajustes.
  3. `ir_attachment.location` es `file`.
  4. Hay configuración S3 válida.
- Organiza objetos por carpeta usando automáticamente `res_model`.
- Regla de transformación del segmento:
  - toma el valor de `res_model` en minúsculas;
  - reemplaza cualquier carácter fuera de `[a-z0-9_-]` por `-`;
  - elimina guiones sobrantes en bordes;
  - limita el resultado a 80 caracteres;
  - si no hay `res_model`, usa `misc/`.

Las claves quedan como:

`<key_prefix_o_db>/<segment>/<sha[:2]>/<sha>`

Ejemplo:

`odoo_prod/product/ab/abcdef1234...`

## Variables de entorno (tienen prioridad)

Si una variable está definida y no vacía, gana sobre el valor en Ajustes:

- `ODOO_S3_BUCKET` (o `AWS_S3_BUCKET`)
- `AWS_DEFAULT_REGION` (o `AWS_REGION`)
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (opcional)
- `AWS_ENDPOINT_URL` (solo para S3-compatible, no necesario en AWS estándar)
- `ODOO_S3_KEY_PREFIX` (opcional)

En despliegue Docker, para evitar que el entrypoint fuerce adjuntos a BD:

- `ODOO_ATTACHMENT_STORAGE=s3`

## Crear un bucket en AWS (guía rápida)

1. Entrar en [AWS Management Console](https://console.aws.amazon.com/).
2. Ir a [S3](https://console.aws.amazon.com/s3/) → **Create bucket**.
3. Elegir nombre único global (ejemplo: `mi-odoo-prod-attachments`).
4. Elegir región (debe coincidir con `AWS_REGION`/`AWS_DEFAULT_REGION`).
5. Mantener **Block Public Access** activado (recomendado).
6. Crear bucket.

Notas:
- No necesitas bucket público para `/web/image`; Odoo lee desde S3 y responde al cliente.
- Versionado, lifecycle y cifrado son recomendables pero opcionales para la integración básica.

Documentación AWS:
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/create-bucket-overview.html

## IAM recomendado (mínimo privilegio)

Crear usuario IAM programático (o rol IAM si ejecutas sobre AWS nativo) con política mínima sobre tu bucket.

Acciones típicas:
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucket` (solo si necesitas listar)

Recursos típicos:
- `arn:aws:s3:::NOMBRE_BUCKET`
- `arn:aws:s3:::NOMBRE_BUCKET/*`

Referencia IAM + S3:
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-policies-s3.html

## Configuración en Odoo

1. Instala el módulo `attachment_s3`.
2. Ve a **Settings**.
3. Activa **Use S3 for file attachments**.
4. Completa bucket/región/credenciales (o usa variables de entorno).
5. Guarda.

Al guardar, el módulo valida conexión al bucket con `HeadBucket`.

## Requisito de almacenamiento Odoo

Este módulo requiere `ir_attachment.location=file`.

- Si usas este repositorio en Docker, usa:
  - `ODOO_ATTACHMENT_STORAGE=s3`
  para que `docker-entrypoint.sh` no fuerce `ir_attachment.location=db`.

## Migración y comportamiento

- Adjuntos nuevos o reescritos tras activar el módulo irán a S3.
- Si el mismo contenido (mismo checksum) se guarda en modelos distintos, puede existir duplicación por carpeta (por ejemplo `product-product/` y `order_bridge-banner/`) por diseño.
- Para migrar adjuntos históricos desde `db`/filestore a esta estructura, planifica una migración controlada (fuera del alcance de este módulo base).

