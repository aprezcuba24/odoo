# Deploy Odoo 19.0 on Seenode

This guide walks you through deploying Odoo 19.0 on [Seenode](https://seenode.com), a modern PaaS similar to Render with managed PostgreSQL, WebSocket support, and automatic SSL.

There are **two deployment modes** available:

- **Runtime mode** (recommended if Dockerfile is not supported): uses `build.sh` + `docker-entrypoint.sh` — [jump to Runtime mode](#runtime-mode-no-dockerfile)
- **Dockerfile mode**: Seenode auto-detects the Dockerfile — [jump to Dockerfile mode](#dockerfile-mode)

## Memory (RAM) requirements

The web service needs enough RAM for **(1)** `odoo-bin -u base` during each deploy before Gunicorn listens on port 8069, and **(2)** Gunicorn workers serving the UI. Both steps load the Odoo stack.

- **Use at least 1GB RAM** for the Odoo web service in production. **`512MB is not supported`** for this setup: the platform OOM killer often stops the process during upgrade or when you navigate heavy screens, which looks like a **restart loop** (repeated entrypoint logs) or **crash after login**.
- If you cannot resize yet: set **`GUNICORN_WORKERS=1`** (or `2`) in the service environment. That reduces memory **after** Gunicorn starts; it does not fix OOM during `odoo-bin -u base`—for that, use a larger instance or temporarily set **`SKIP_DB_UPGRADE=true`** and run `odoo-bin -u base` manually from an environment with sufficient RAM (same `DATABASE_URL`).
- **Exit code 137** in logs often indicates OOM.

---

## Runtime mode (no Dockerfile)

Use this mode when Seenode does not allow Dockerfile-based deployments and instead asks for a runtime, build command, and start command.

### Why `pip install -r requirements.txt` fails alone

Odoo requires several native C libraries (`libpq-dev`, `libxml2-dev`, `libsass-dev`, `libldap2-dev`, etc.) to be present **before** pip can compile its Python dependencies. The `build.sh` script installs those system libraries first and then runs pip.

### 1. Push code to GitHub

```bash
git add -A
git commit -m "Add build.sh for Seenode runtime deployment"
git push origin main
```

### 2. Create PostgreSQL database

1. In the Seenode dashboard go to **Databases** → **Create database**
2. Choose **PostgreSQL** (version 16 recommended)
3. Wait for provisioning and copy the **Connection URL**

### 3. Create Web Service

1. Click **New** → **Web Service** → connect your GitHub repository
2. Select the branch (`main`)
3. Choose a **Python runtime** (Python 3.12 recommended)
4. Set the following:

| Field | Value |
|-------|-------|
| **Port** | `8069` |
| **Build command** | `bash build.sh` |
| **Start command** | `bash docker-entrypoint.sh` |

### 4. Configure environment variables

| Variable | Value | Description |
|----------|-------|-------------|
| `DATABASE_URL` | Connection URL from step 2 | Full PostgreSQL URI |
| `DB_PASSWORD_ADMIN` | Strong password | Odoo master password |
| `DB_LANGUAGE` | `es_ES` | Default language |
| `DB_USERNAME` | `admin` | Default admin username |
| `DB_WITH_DEMO` | `false` | No demo data in production |

Optional deploy / resource tuning:

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_DB_UPGRADE` | *unset* | Set `true` to skip `odoo-bin -u base` on startup (emergency only; run upgrade manually) |
| `GUNICORN_WORKERS` | `2` | Use `1` on very small instances to limit RAM while browsing |
| `GUNICORN_TIMEOUT` | `600` | Request timeout in seconds |
| `GUNICORN_KEEPALIVE` | `75` | Keep-alive timeout |

### 5. Deploy

Click **Create Web Service**. The first deployment:
1. `build.sh` installs system libraries and Python packages (~3-5 min)
2. `docker-entrypoint.sh` initialises the database schema (~3-5 min)
3. Gunicorn starts and health checks pass

Subsequent deployments skip the full system install (cached by Seenode) and only run the database upgrade.

---

## Dockerfile mode

## Prerequisites

- GitHub or GitLab account (for repository connection)
- This repository already configured with the required Dockerfile and Gunicorn setup

## What Changed for Seenode Compatibility

The codebase has been updated with the following changes:

| File | Changes |
|------|---------|
| `docker-entrypoint.sh` | Paths changed from `/apps/odoo/` to `/app` to match Dockerfile WORKDIR |
| `Dockerfile` | `GUNICORN_WORKER_CLASS` changed to `gunicorn_gevent_handler.GeventWorkerWithSocket` for WebSocket support |
| `Dockerfile` | Logs now output to stdout/stderr (`-`) for PaaS visibility |
| `gunicorn.conf.py` | pidfile changed to `/tmp/gunicorn.pid` for container compatibility |
| `gunicorn.conf.py` | `worker_tmp_dir` changed to `/tmp` for better PaaS support |
| `.env.example` | Added Seenode deployment examples |

## Deployment Steps

### 1. Push Code to GitHub

Ensure your repository is pushed to GitHub with all the updated files:

```bash
git add -A
git commit -m "Configure for PaaS deployment (Seenode/Railway/Render compatible)"
git push origin main
```

### 2. Sign Up for Seenode

Go to [cloud.seenode.com](https://cloud.seenode.com) and sign in with GitHub.

### 3. Create PostgreSQL Database

1. Navigate to **Databases** in the sidebar
2. Click **Create first database**
3. Configure:
   - **Name**: `odoo-db` (or any name)
   - **Type**: PostgreSQL
   - **Version**: 16 (or 15+)
   - **Tier**: Choose based on your needs (minimum Tier 2: 1GB recommended for Odoo)
4. Click **Create database**
5. Wait for the database to be provisioned (~1 minute)
6. Copy the **Connection URL** from the database dashboard (format: `postgresql://postgres:password@db-...`)

### 4. Deploy Web Service

1. Click **New** → **Web Service**
2. Connect your GitHub repository
3. Select your Odoo repository and branch (usually `main`)
4. Configure:
   - **Name**: `odoo` (or your preference)
   - **Port**: `8069` (must match `GUNICORN_BIND`)
   - **Build Command**: (leave empty - Dockerfile is auto-detected)
   - **Start Command**: (leave empty - ENTRYPOINT is in Dockerfile)
5. Click **Continue**

### 5. Configure Environment Variables

In the service dashboard, add these environment variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `DATABASE_URL` | Your database connection URL | From step 3 |
| `DB_PASSWORD_ADMIN` | Strong password | Odoo master password |
| `DB_LANGUAGE` | `es_ES` | Default language |
| `DB_USERNAME` | `admin` | Default admin username |
| `DB_WITH_DEMO` | `false` | No demo data in production |

Optional deploy / Gunicorn overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_DB_UPGRADE` | *unset* | Set `true` to skip `odoo-bin -u base` on startup (emergency only; run upgrade manually) |
| `GUNICORN_WORKERS` | 2 | Number of workers (`1` for minimal RAM) |
| `GUNICORN_TIMEOUT` | 600 | Request timeout (seconds) |
| `GUNICORN_KEEPALIVE` | 75 | Keep-alive timeout (seconds) |

### 6. Deploy

Click **Create Web Service**.

**Note:** First deployment takes 5-10 minutes because:
1. Docker builds the image (~2-3 min)
2. `docker-entrypoint.sh` initializes the database schema (~3-5 min)
3. Gunicorn starts serving requests

### 7. Access Your Application

Once deployed, you'll receive a URL like:
```
https://odoo-[your-instance].up-de-fra1-k8s-1.apps.run-on-seenode.com
```

Visit this URL to access Odoo.

**Important:** On first access:
1. Create your admin account using the credentials from `DB_USERNAME` and `DB_PASSWORD_ADMIN`
2. Install the apps you need

### 8. Verify WebSocket Support

WebSockets enable real-time features (Discuss, live chat, notifications):

1. Log into Odoo
2. Open the Discuss app or start a conversation
3. If messages appear instantly without page refresh, WebSockets are working

If not, check the logs in the Seenode dashboard for WebSocket connection errors.

## Subsequent Deploys

Every push to your connected branch triggers a new deployment:

1. **Zero-downtime**: The old instance stays up while the new one starts
2. **Automatic upgrade**: `docker-entrypoint.sh` runs `odoo-bin -u base` to update the database schema
3. **Switch**: Traffic routes to the new instance once healthy

**Deploy time:** 3-5 minutes (database upgrade takes ~2-3 min)

## Monitoring and Logs

### View Logs
1. Go to your service dashboard
2. Click the **Logs** tab
3. See real-time stdout/stderr output from Gunicorn and Odoo

### Health Checks
The Dockerfile includes a healthcheck that verifies `/web/health` responds, with a **long start period** (one hour) so the check does not fail while `odoo-bin -u base` is still running before Gunicorn binds port 8069. Seenode uses this (or equivalent probes) to determine if the deployment is healthy.

## File Storage Considerations

**⚠️ Important:** Seenode does not currently offer persistent volumes. By default, Odoo stores uploaded files (attachments, documents) on the filesystem.

### Options:

1. **Database Storage** (Recommended for small deployments)
   - Configure Odoo to store attachments in the database
   - Increases database size but no external dependencies
   - Add to environment: `ODOO_ATTACHMENT_STORAGE=db`

2. **External S3-Compatible Storage**
   - Use AWS S3, DigitalOcean Spaces, MinIO, etc.
   - Requires installing `boto3` and configuring Odoo storage backend
   - See Odoo documentation for S3 attachment storage

3. **Use as-is**
   - Files will be lost on redeploy
   - Not recommended for production

## Troubleshooting

### Build Fails
- Check that all required files are committed to GitHub
- Ensure `requirements.txt` exists and is valid
- Review build logs for Python dependency errors

### App Not Responding
- Verify **Port** is set to `8069` in service settings
- Check logs for database connection errors
- Ensure `DATABASE_URL` is correctly set

### Database Connection Errors
- Verify the database is running in Seenode dashboard
- Check that `DATABASE_URL` matches the connection URL from the database
- Test: `psql "${DATABASE_URL}" -c "SELECT 1"`

### WebSocket Issues
- Check logs for errors like "EBADF" or "Socket error" (these are expected and suppressed)
- Verify Gunicorn worker class is `gunicorn_gevent_handler.GeventWorkerWithSocket`
- Ensure WebSocket features work in Odoo (Discuss app)

### Slow First Deploy
- First deployment initializes the database (normal)
- Subsequent deploys are faster (3-5 min)
- Increase instance size if database initialization times out

### Deploy loop, or crash after login when opening menus

These usually mean the **container was killed and restarted** (not a random Odoo bug).

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| `[INFO] DATABASE_URL detectada...` repeats from the top | OOM during `odoo-bin -u base`, or (less often) health check timing if RAM is already sufficient | Increase web service to **≥1GB RAM**. Optionally `SKIP_DB_UPGRADE=true` once, then run `odoo-bin -u base` manually with enough memory. |
| Login works, then session dies when navigating | OOM during normal requests (multiple workers × Odoo RSS) | **≥1GB RAM** and/or **`GUNICORN_WORKERS=1`**. |
| Exit code **137** in logs | Often **OOM killer** | Increase RAM; reduce workers. |

Confirm in platform logs: messages like **out of memory** or **512MB** limits.

### Health check failures during long upgrades

If the database upgrade step reliably takes many minutes and the platform still replaces instances before Gunicorn starts, ensure the **Docker healthcheck start period** in [`Dockerfile`](Dockerfile) is long enough for your environment (default is **3600s**), and align any Seenode deploy grace / probe settings if available.

## Scaling

### Vertical Scaling (More Resources)
1. Go to service dashboard
2. Upgrade instance tier (CPU/RAM)
3. Redeploy

### Horizontal Scaling (More Instances)
Seenode supports multiple instances:
1. Configure **Instances** count in service settings
2. **⚠️ Warning:** Multiple Odoo instances require:
   - Shared session storage (configure Redis or database sessions)
   - Shared file storage (S3 or database attachments)
   - See Odoo documentation for multi-instance setup

## Cost Estimates

| Component | Minimal | Recommended |
|-----------|---------|-------------|
| App (Web Service) | *512MB tiers are not suitable for this Odoo image* | **1GB+** / typical starter pricing |
| Database (Tier 2) | 1GB storage / $5/mo | 5GB storage / $10/mo |
| **Total** | Plan for **≥1GB app RAM** + DB | Scale with workload |

*Prices based on Seenode pricing at time of writing. Check [seenode.com/pricing](https://seenode.com/pricing) for current rates.*

## Support

- Seenode Discord: [discord.com/invite/d2gATEMFSc](https://discord.com/invite/d2gATEMFSc)
- Seenode Email: [help@seenode.com](mailto:help@seenode.com)
- Odoo Community: [odoo.com/forum](https://www.odoo.com/forum)

## Alternatives

If Seenode doesn't meet your needs, this same codebase works with:
- **Railway**: Almost identical setup, DATABASE_URL auto-configured
- **Render**: Use `render.yaml` for infrastructure-as-code
- **Fly.io**: Add `fly.toml` and use `fly deploy`
- **DigitalOcean App Platform**: Docker-based deployment

The Dockerfile-based approach makes this portable across any Docker-compatible PaaS.
