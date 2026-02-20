# Odoo

[![Build Status](https://runbot.odoo.com/runbot/badge/flat/1/master.svg)](https://runbot.odoo.com/runbot)
[![Tech Doc](https://img.shields.io/badge/master-docs-875A7B.svg?style=flat&colorA=8F8F8F)](https://www.odoo.com/documentation/master)
[![Help](https://img.shields.io/badge/master-help-875A7B.svg?style=flat&colorA=8F8F8F)](https://www.odoo.com/forum/help-1)
[![Nightly Builds](https://img.shields.io/badge/master-nightly-875A7B.svg?style=flat&colorA=8F8F8F)](https://nightly.odoo.com/)

Odoo is a suite of web based open source business apps.

The main Odoo Apps include an [Open Source CRM](https://www.odoo.com/page/crm),
[Website Builder](https://www.odoo.com/app/website),
[eCommerce](https://www.odoo.com/app/ecommerce),
[Warehouse Management](https://www.odoo.com/app/inventory),
[Project Management](https://www.odoo.com/app/project),
[Billing &amp; Accounting](https://www.odoo.com/app/accounting),
[Point of Sale](https://www.odoo.com/app/point-of-sale-shop),
[Human Resources](https://www.odoo.com/app/employees),
[Marketing](https://www.odoo.com/app/social-marketing),
[Manufacturing](https://www.odoo.com/app/manufacturing),
[...](https://www.odoo.com/)

Odoo Apps can be used as stand-alone applications, but they also integrate seamlessly so you get
a full-featured [Open Source ERP](https://www.odoo.com) when you install several Apps.

## Getting started with Odoo

For a standard installation please follow the [Setup instructions](https://www.odoo.com/documentation/master/administration/install/install.html)
from the documentation.

To learn the software, we recommend the [Odoo eLearning](https://www.odoo.com/slides),
or [Scale-up, the business game](https://www.odoo.com/page/scale-up-business-game).
Developers can start with [the developer tutorials](https://www.odoo.com/documentation/master/developer/howtos.html).

## Security

If you believe you have found a security issue, check our [Responsible Disclosure page](https://www.odoo.com/security-report)
for details and get in touch with us via email.

---

## Docker Deployment Guide

This guide covers deploying Odoo 19.0 in production using Docker with an external PostgreSQL database.

### Table of Contents

- [Prerequisites](#prerequisites)
- [External Database Setup](#external-database-setup)
- [Production Deployment](#production-deployment)
- [Cloud Platform Deployment](#cloud-platform-deployment)
- [Configuration Reference](#configuration-reference)
- [Database Management](#database-management)
- [Local Development](#local-development)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)
- [Monitoring and Logs](#monitoring-and-logs)

---

### Prerequisites

Before deploying Odoo, ensure you have:

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **External PostgreSQL Database**: Version 13 or higher (required)
  - Cloud options: AWS RDS, Google Cloud SQL, Azure Database, Railway, DigitalOcean, etc.
  - Self-hosted: PostgreSQL server accessible from your Docker host
- **System Resources** (for Odoo application):
  - Minimum: 2 CPU cores, 4GB RAM
  - Recommended: 4 CPU cores, 8GB RAM
  - Storage: 20GB+ for application data

**Important**: This production setup uses an **external PostgreSQL database**. The database is NOT included in docker-compose.yml and must be provisioned separately.

---

### External Database Setup

#### 1. Choose Your Database Provider

Select one of the following options:

**Cloud Providers** (Recommended for production):
- **Railway**: Easy setup, auto-scaling, built-in backups
- **AWS RDS**: Enterprise-grade, Multi-AZ support, automated backups
- **Google Cloud SQL**: Managed PostgreSQL with high availability
- **Azure Database**: Integrated with Azure services
- **DigitalOcean**: Managed databases with simple pricing

**Self-Hosted**:
- PostgreSQL 13+ installed on a separate server or VM
- Properly configured for remote connections
- Regular backup strategy in place

#### 2. Create PostgreSQL Database

Example using Railway:
```bash
# 1. Create new project in Railway dashboard
# 2. Add PostgreSQL service
# 3. Note the connection details provided
```

Example using AWS RDS:
```bash
# 1. Create RDS PostgreSQL instance via AWS Console
# 2. Configure security group to allow connections from Odoo server
# 3. Note the endpoint, port, username, and password
```

Example using self-hosted PostgreSQL:
```bash
# On your PostgreSQL server:
sudo -u postgres psql

# Create database and user:
CREATE DATABASE odoo;
CREATE USER odoo WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE odoo TO odoo;
\q

# Configure pg_hba.conf to allow remote connections
# Edit postgresql.conf: listen_addresses = '*'
# Restart PostgreSQL
```

#### 3. Obtain Database Connection String

Your DATABASE_URL should look like:
```
postgresql://[username]:[password]@[host]:[port]/[database]?sslmode=require
```

Examples:
- Railway: `postgresql://postgres:pass@postgres.railway.internal:5432/odoo`
- AWS RDS: `postgresql://odoo:pass@mydb.xxxx.us-east-1.rds.amazonaws.com:5432/odoo?sslmode=require`
- Google Cloud: `postgresql://odoo:pass@34.123.45.67:5432/odoo?sslmode=require`
- Self-hosted: `postgresql://odoo:pass@192.168.1.100:5432/odoo`

#### 4. Test Database Connection

```bash
# Using psql client
psql "postgresql://user:password@host:5432/odoo" -c "SELECT version();"

# Or using Docker
docker run --rm postgres:16-alpine \
  psql "postgresql://user:password@host:5432/odoo" -c "SELECT 1"
```

If the connection fails, verify:
- Database host is reachable
- Credentials are correct
- Firewall/security groups allow connections
- SSL settings match database requirements

---

### Production Deployment

#### 1. Clone Repository

```bash
git clone <repository-url>
cd odoo
```

#### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

**Required changes in .env**:
```bash
# Set your external database URL
DATABASE_URL=postgresql://user:password@your-db-host:5432/odoo?sslmode=require

# Set secure admin password
DB_PASSWORD_ADMIN=your_secure_master_password

# Configure language (optional)
DB_LANGUAGE=es_ES

# Disable demo data for production
DB_WITH_DEMO=false

# Adjust Gunicorn workers based on CPU cores
GUNICORN_WORKERS=4
```

#### 3. Deploy Application

```bash
# Build and start Odoo container
docker-compose up -d --build

# Check container status (should show "healthy" after ~5 minutes)
docker-compose ps

# Follow logs to monitor initialization
docker-compose logs -f odoo
```

On first run, the entrypoint script will:
- Connect to the external PostgreSQL database
- Create necessary tables and schema
- Initialize Odoo database with configured language
- Set the master password

#### 4. Access Odoo

Open your browser:
```
http://localhost:8069
```

Or if deployed on a server:
```
http://your-server-ip:8069
```

**Default credentials**:
- Username: `admin`
- Password: Value of `DB_PASSWORD_ADMIN` from .env

#### 5. Configure Reverse Proxy (Recommended)

For production, use a reverse proxy with SSL/TLS:

**Nginx example**:
```nginx
server {
    listen 80;
    server_name odoo.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name odoo.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    proxy_read_timeout 600s;
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;

    location / {
        proxy_pass http://localhost:8069;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_redirect off;
    }

    # WebSocket support
    location /websocket {
        proxy_pass http://localhost:8069/websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Traefik example** (docker-compose.yml addition):
```yaml
services:
  odoo:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.odoo.rule=Host(`odoo.example.com`)"
      - "traefik.http.routers.odoo.entrypoints=websecure"
      - "traefik.http.routers.odoo.tls.certresolver=letsencrypt"
      - "traefik.http.services.odoo.loadbalancer.server.port=8069"
```

---

### Cloud Platform Deployment

#### Railway

Railway provides the simplest deployment experience:

1. **Create Railway Project**:
   - Visit [railway.app](https://railway.app)
   - Create new project
   - Add PostgreSQL service (automatic provisioning)

2. **Deploy Odoo**:
   ```bash
   # Install Railway CLI
   npm i -g @railway/cli

   # Login and link project
   railway login
   railway link

   # Set environment variables
   railway variables set DATABASE_URL="postgresql://postgres:password@postgres.railway.internal:5432/odoo"
   railway variables set DB_PASSWORD_ADMIN="your_secure_password"

   # Deploy
   railway up
   ```

3. **Access Application**:
   - Railway provides automatic HTTPS domain
   - Access via: `https://your-app.railway.app`

#### AWS (ECS/Fargate)

1. **Create RDS PostgreSQL Instance**:
   ```bash
   # Use AWS Console or CLI
   aws rds create-db-instance \
     --db-instance-identifier odoo-db \
     --db-instance-class db.t3.medium \
     --engine postgres \
     --engine-version 16.1 \
     --master-username odoo \
     --master-user-password your_password \
     --allocated-storage 20
   ```

2. **Create ECS Task Definition**:
   - Use the production Dockerfile
   - Configure environment variables
   - Set DATABASE_URL to RDS endpoint
   - Configure EFS volume for persistent storage

3. **Deploy to ECS**:
   - Create ECS cluster
   - Define service with load balancer
   - Configure auto-scaling

#### Google Cloud (Cloud Run)

1. **Create Cloud SQL Instance**:
   ```bash
   gcloud sql instances create odoo-db \
     --database-version=POSTGRES_16 \
     --tier=db-custom-2-7680 \
     --region=us-central1
   ```

2. **Build and Push Container**:
   ```bash
   # Build image
   docker build -t gcr.io/your-project/odoo:latest .

   # Push to Container Registry
   docker push gcr.io/your-project/odoo:latest
   ```

3. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy odoo \
     --image gcr.io/your-project/odoo:latest \
     --add-cloudsql-instances your-project:us-central1:odoo-db \
     --set-env-vars DATABASE_URL="postgresql://..." \
     --allow-unauthenticated
   ```

#### Heroku

1. **Create Heroku App**:
   ```bash
   heroku create your-odoo-app
   heroku addons:create heroku-postgresql:standard-0
   ```

2. **Configure and Deploy**:
   ```bash
   # Set environment variables
   heroku config:set DB_PASSWORD_ADMIN="your_password"

   # Deploy
   git push heroku main
   ```

---

### Configuration Reference

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | *required* | PostgreSQL connection string (external database) |
| `PGHOST` | - | Database host (alternative to DATABASE_URL) |
| `PGPORT` | 5432 | Database port |
| `PGUSER` | - | Database username |
| `PGPASSWORD` | - | Database password |
| `PGDATABASE` | odoo | Database name |
| `DB_PASSWORD_ADMIN` | changeme | Odoo master password (change in production!) |
| `DB_LANGUAGE` | es_ES | Default language (en_US, es_ES, fr_FR, etc.) |
| `DB_WITH_DEMO` | false | Install demo data (set to false in production) |
| `GUNICORN_WORKERS` | 4 | Number of worker processes (2-4 per CPU core) |
| `GUNICORN_TIMEOUT` | 600 | Request timeout in seconds |
| `GUNICORN_KEEPALIVE` | 75 | Keep-alive timeout in seconds |
| `GUNICORN_MAX_REQUESTS` | 0 | Max requests before worker restart (0=disabled) |
| `GUNICORN_MAX_REQUESTS_JITTER` | 0 | Jitter for max_requests |

#### WebSocket Configuration

Odoo uses WebSockets for real-time features (live chat, notifications, etc.). The production setup includes:

- **Gunicorn worker class**: `gevent` (configured in gunicorn.conf.py)
- **Custom gevent handler**: Handles WebSocket connections
- **WebSocket endpoint**: `/websocket`

If using a reverse proxy, ensure WebSocket headers are forwarded:
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

#### Resource Recommendations

**Small deployment** (< 10 users):
- Odoo: 2 CPU cores, 4GB RAM
- Database: 2 CPU cores, 4GB RAM
- Workers: 2-4

**Medium deployment** (10-50 users):
- Odoo: 4 CPU cores, 8GB RAM
- Database: 4 CPU cores, 8GB RAM
- Workers: 8-12

**Large deployment** (50+ users):
- Odoo: 8+ CPU cores, 16+ GB RAM
- Database: 8+ CPU cores, 16+ GB RAM
- Workers: 16-24
- Consider horizontal scaling with load balancer

---

### Database Management

#### Backup Database

**Using pg_dump**:
```bash
# Backup to file
pg_dump "$DATABASE_URL" > odoo_backup_$(date +%Y%m%d).sql

# Backup with compression
pg_dump "$DATABASE_URL" | gzip > odoo_backup_$(date +%Y%m%d).sql.gz
```

**Using Docker**:
```bash
docker run --rm postgres:16-alpine \
  pg_dump "$DATABASE_URL" > odoo_backup_$(date +%Y%m%d).sql
```

**Backup filestore** (Odoo attachments):
```bash
# Create backup of odoo-data volume
docker run --rm -v odoo_odoo-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/odoo-filestore-$(date +%Y%m%d).tar.gz /data
```

#### Restore Database

```bash
# Restore from SQL file
psql "$DATABASE_URL" < odoo_backup.sql

# Restore from compressed file
gunzip -c odoo_backup.sql.gz | psql "$DATABASE_URL"
```

**Restore filestore**:
```bash
# Extract filestore backup to volume
docker run --rm -v odoo_odoo-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/odoo-filestore.tar.gz -C /
```

#### Database Maintenance

```bash
# Access database
psql "$DATABASE_URL"

# Vacuum database
VACUUM ANALYZE;

# Check database size
SELECT pg_size_pretty(pg_database_size('odoo'));

# List connections
SELECT * FROM pg_stat_activity WHERE datname = 'odoo';
```

#### Migration

When upgrading Odoo versions:

1. **Backup everything**:
   ```bash
   pg_dump "$DATABASE_URL" > backup_before_upgrade.sql
   docker run --rm -v odoo_odoo-data:/data -v $(pwd):/backup \
     alpine tar czf /backup/filestore_before_upgrade.tar.gz /data
   ```

2. **Update Dockerfile** to new Odoo version

3. **Rebuild and restart**:
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

4. **Monitor logs**:
   ```bash
   docker-compose logs -f odoo
   ```

5. **Update modules** (via Odoo UI or CLI)

---

### Local Development

For local development with VS Code, use the `.devcontainer` configuration which includes a local PostgreSQL service:

```bash
# Open in VS Code
code .

# When prompted, select "Reopen in Container"
# Or use Command Palette: "Dev Containers: Reopen in Container"
```

**Development environment includes**:
- Odoo application service
- PostgreSQL 16 service (local, not external)
- All development tools and extensions
- Automatic port forwarding
- Live reload with `--dev=all` flag

**Key differences from production**:
- Uses `.devcontainer/Dockerfile` (includes dev tools)
- Includes local PostgreSQL container
- Code mounted as volume for live editing
- Runs `odoo-bin` directly (not Gunicorn)
- Demo data enabled

---

### Troubleshooting

#### Container Won't Start

```bash
# Check logs
docker-compose logs odoo

# Common issues:
# 1. Database connection failed
#    - Verify DATABASE_URL is correct
#    - Check database is accessible
#    - Verify credentials

# 2. Port already in use
docker ps  # Check if port 8069 is used
# Solution: Stop conflicting container or change port in docker-compose.yml

# 3. Build errors
docker-compose build --no-cache  # Rebuild without cache
```

#### Database Connection Issues

```bash
# Test connection
docker run --rm postgres:16-alpine \
  psql "$DATABASE_URL" -c "SELECT 1"

# Check connection from container
docker-compose exec odoo bash
psql "$DATABASE_URL" -c "SELECT version();"

# Verify environment variables
docker-compose exec odoo env | grep -E "(DATABASE_URL|PG)"
```

#### Health Check Failing

```bash
# Check health endpoint manually
docker-compose exec odoo curl -f http://localhost:8069/web/health

# If fails, check:
# 1. Odoo is running
docker-compose exec odoo ps aux | grep odoo

# 2. Port is listening
docker-compose exec odoo netstat -tlnp | grep 8069

# 3. Database is initialized
docker-compose logs odoo | grep -i "database\|inicializada"
```

#### WebSocket Not Working

```bash
# 1. Verify gevent is working
docker-compose exec odoo python -c "import gevent; print(gevent.__version__)"

# 2. Check WebSocket endpoint
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://localhost:8069/websocket

# 3. If using reverse proxy, ensure headers are forwarded:
#    - Upgrade: websocket
#    - Connection: Upgrade
```

#### Performance Issues

```bash
# Check container resources
docker stats

# Increase workers if CPU allows
# Edit .env:
GUNICORN_WORKERS=8

# Restart
docker-compose restart odoo

# Check database performance
psql "$DATABASE_URL" -c "
  SELECT schemaname, tablename,
         pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
  LIMIT 10;"

# Monitor slow queries
psql "$DATABASE_URL" -c "
  SELECT pid, now() - query_start as duration, query
  FROM pg_stat_activity
  WHERE state = 'active'
  ORDER BY duration DESC;"
```

#### Disk Space Issues

```bash
# Check volume sizes
docker system df -v

# Clean up unused images/containers
docker system prune -a

# Check database size
psql "$DATABASE_URL" -c "SELECT pg_size_pretty(pg_database_size('odoo'));"

# Vacuum database to reclaim space
psql "$DATABASE_URL" -c "VACUUM FULL;"
```

#### Reset Everything

```bash
# WARNING: This will delete all data!

# Stop and remove containers
docker-compose down -v

# Remove volumes (DESTRUCTIVE!)
docker volume rm odoo_odoo-data odoo_odoo-logs

# Drop and recreate database (on database server)
psql "$DATABASE_URL" -c "DROP DATABASE odoo;"
psql "$DATABASE_URL" -c "CREATE DATABASE odoo;"

# Restart
docker-compose up -d --build
```

---

### Security Best Practices

#### Production Security Checklist

- [ ] **Change default passwords**
  - Set strong `DB_PASSWORD_ADMIN`
  - Change Odoo admin password after first login

- [ ] **Enable SSL/TLS**
  - Use `sslmode=require` in DATABASE_URL
  - Configure HTTPS reverse proxy
  - Use Let's Encrypt for free certificates

- [ ] **Secure database access**
  - Use private networking for database (no public IP)
  - Restrict database firewall to Odoo server IP only
  - Use strong database passwords

- [ ] **Protect sensitive files**
  - Never commit .env to version control
  - Restrict .env file permissions: `chmod 600 .env`
  - Use secrets management (AWS Secrets Manager, Vault, etc.)

- [ ] **Network security**
  - Don't expose port 8069 directly (use reverse proxy)
  - Enable firewall on server
  - Use VPC/private networking in cloud

- [ ] **Regular updates**
  - Keep Docker images updated
  - Apply Odoo security patches
  - Update PostgreSQL regularly

- [ ] **Backups**
  - Automated daily database backups
  - Backup filestore volumes
  - Test restore procedures
  - Store backups off-site

- [ ] **Monitoring**
  - Set up uptime monitoring
  - Configure alerting for errors
  - Monitor resource usage
  - Track failed login attempts

- [ ] **Rate limiting**
  - Configure nginx/Traefik rate limiting
  - Protect against brute force attacks

- [ ] **Logging**
  - Centralize logs (ELK, Datadog, CloudWatch)
  - Monitor for security events
  - Retain logs for audit purposes

#### Secrets Management

For production, use dedicated secrets management:

**AWS Secrets Manager**:
```bash
# Store DATABASE_URL
aws secretsmanager create-secret \
  --name odoo/database-url \
  --secret-string "$DATABASE_URL"

# Retrieve in application
export DATABASE_URL=$(aws secretsmanager get-secret-value \
  --secret-id odoo/database-url \
  --query SecretString --output text)
```

**HashiCorp Vault**:
```bash
# Store secret
vault kv put secret/odoo database_url="$DATABASE_URL"

# Retrieve secret
vault kv get -field=database_url secret/odoo
```

**Docker Secrets** (Swarm mode):
```bash
# Create secret
echo "$DATABASE_URL" | docker secret create database_url -

# Use in docker-compose.yml:
secrets:
  database_url:
    external: true
services:
  odoo:
    secrets:
      - database_url
```

---

### Monitoring and Logs

#### View Logs

```bash
# Real-time logs
docker-compose logs -f odoo

# Last 100 lines
docker-compose logs --tail=100 odoo

# Search logs
docker-compose logs odoo | grep ERROR

# Export logs
docker-compose logs --no-color odoo > odoo.log
```

#### Access Log Files

Logs are stored in the `odoo-logs` volume:

```bash
# Access log volume
docker run --rm -v odoo_odoo-logs:/logs alpine ls -lah /logs

# Copy logs to host
docker run --rm -v odoo_odoo-logs:/logs -v $(pwd):/backup \
  alpine cp -r /logs /backup/odoo-logs
```

#### Health Monitoring

```bash
# Check health status
docker-compose ps

# Health endpoint
curl http://localhost:8069/web/health

# Detailed health check
docker inspect --format='{{json .State.Health}}' odoo-production | jq
```

#### Resource Monitoring

```bash
# Real-time stats
docker stats odoo-production

# CPU and memory usage
docker stats --no-stream odoo-production

# Disk usage
docker system df -v | grep odoo
```

#### Application Monitoring

Consider integrating with:

- **Prometheus + Grafana**: Metrics and dashboards
- **New Relic**: APM and monitoring
- **Datadog**: Infrastructure and application monitoring
- **Sentry**: Error tracking
- **ELK Stack**: Log aggregation and analysis

#### Database Monitoring

```bash
# Active connections
psql "$DATABASE_URL" -c "
  SELECT count(*) as connections,
         state
  FROM pg_stat_activity
  WHERE datname = 'odoo'
  GROUP BY state;"

# Database size growth
psql "$DATABASE_URL" -c "
  SELECT pg_size_pretty(pg_database_size('odoo'));"

# Table sizes
psql "$DATABASE_URL" -c "
  SELECT schemaname, tablename,
         pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
  LIMIT 10;"

# Slow queries (if pg_stat_statements enabled)
psql "$DATABASE_URL" -c "
  SELECT calls, mean_exec_time, query
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;"
```

---

## Bare-Metal Deployment (Debian VPS)

Use `deploy.sh` to install Odoo 19.0 directly on a Debian (or Ubuntu) VPS — no Docker required. The script sets up system packages, Python 3.12, wkhtmltopdf, a virtualenv, and a systemd service.

### Prerequisites

- **Debian 12 (Bookworm)** or Ubuntu 22.04+ VPS
- Root access (run as `sudo`)
- App code already cloned at `/apps/odoo`
- An external **PostgreSQL 13+** database accessible from the VPS (connection URL ready)
- `odoo.service` present in the same directory as `deploy.sh`

### Step 1 — Clone the repository

```bash
sudo mkdir -p /apps
sudo git clone <repository-url> /apps/odoo
```

### Step 2 — Run the deployment script

```bash
cd /apps/odoo
sudo bash deploy.sh
# Also works on Debian with sh:
sudo sh deploy.sh
```

The script will:
1. Install system packages (`build-essential`, `libpq-dev`, fonts, etc.)
2. Install **Python 3.12** via the `deadsnakes` PPA if not already present
3. Install **wkhtmltopdf** 0.12.6.1 (Bookworm build)
4. Create the `odoo` system user and directories (`/var/log/odoo`, `/var/run/odoo`)
5. Patch internal path references in `docker-entrypoint.sh`
6. Create a Python virtualenv at `/apps/odoo/venv` and install all dependencies
7. Create `/apps/odoo/.env` from `.env.example` (or from a built-in template)
8. Install and enable the `odoo` systemd service

### Step 3 — Configure the environment

The script pauses and asks you to confirm that `DATABASE_URL` is set. Edit the file before answering:

```bash
sudo nano /apps/odoo/.env
```

Required variables:

```bash
# PostgreSQL connection URI
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Gunicorn
GUNICORN_BIND=0.0.0.0:8069
GUNICORN_WORKERS=4

# Odoo admin password (change this!)
DB_PASSWORD_ADMIN=your_secure_password
DB_LANGUAGE=es_ES
DB_WITH_DEMO=false
```

Answer `s` (yes) at the prompt to start the service immediately, or `N` to start it manually later.

### Step 4 — Start and verify

```bash
# Check service status
sudo systemctl status odoo

# Follow live logs
sudo journalctl -u odoo -f

# Health check
curl http://localhost:8069/web/health
```

Access Odoo at `http://<your-server-ip>:8069`.

### Updating configuration (.env changes)

After editing `/apps/odoo/.env`, restart the service so systemd re-reads the file:

```bash
sudo nano /apps/odoo/.env       # make your changes
sudo systemctl restart odoo     # picks up the new values
sudo journalctl -u odoo -f      # confirm the service started correctly
```

> **Note:** `systemctl daemon-reload` is only needed when the `odoo.service` unit file itself
> changes (e.g. after a `git pull` that updated it). For `.env`-only changes a plain
> `restart` is sufficient.

To verify a variable was loaded:
```bash
sudo systemctl show odoo --property=Environment
```

### Re-running the script

The script is **idempotent**: it skips steps that are already done (existing user, existing virtualenv, existing wkhtmltopdf, etc.). You can safely re-run it after pulling updates or changing configuration.

```bash
cd /apps/odoo
git pull
sudo bash deploy.sh
```

### Troubleshooting

**Service fails to start**
```bash
sudo journalctl -u odoo -n 50
# Look for database connection errors or missing env vars
```

**Database connection refused**
```bash
# Test connectivity from the VPS
psql "$DATABASE_URL" -c "SELECT 1;"
# Verify firewall/security groups allow port 5432 from this IP
```

**Port 8069 not reachable**
```bash
# Check if ufw is active
sudo ufw status
# Open port manually if needed
sudo ufw allow 8069/tcp
```

**Python 3.12 not found after PPA install**
```bash
python3.12 --version
# If missing, add the PPA and install manually:
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
```

---

## Additional Resources

- [Official Odoo Documentation](https://www.odoo.com/documentation/19.0/)
- [Odoo Developer Documentation](https://www.odoo.com/documentation/19.0/developer.html)
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)

## Support

For issues specific to this Docker deployment:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review container logs: `docker-compose logs odoo`
3. Verify configuration in `.env` file
4. Test database connectivity

For Odoo-specific issues:
- [Odoo Community Forum](https://www.odoo.com/forum/help-1)
- [Odoo GitHub Issues](https://github.com/odoo/odoo/issues)
