# Docker (Traefik TLS) + Grafana/Prometheus monitoring

This replaces a "manual" install (gunicorn/systemd + reverse-proxy) with a fully containerised stack **while keeping the same external behaviour**:

- **HTTP(80)** → redirect to **HTTPS(443)**
- **HTTPS(443)** serves the Audela Flask site (public pages + `/app`)
- TLS certificates supported **either** by mounting existing certs **or** by auto-provisioning with Let's Encrypt.

It also adds **environment monitoring**:
- **Prometheus** scrapes host + container + DB + Redis + Traefik metrics
- **Grafana** (pre-provisioned Prometheus datasource + basic dashboard)

## Files added

- `Dockerfile` (builds the Flask app)
- `docker-compose.yml` (TLS using your existing cert files)
- `docker-compose.letsencrypt.yml` (optional override to use Let's Encrypt)
- `docker/entrypoint.sh` (wait DB + migrations + gunicorn)
- `prometheus/prometheus.yml`
- `grafana/provisioning/...` + `grafana/dashboards/system.json`
- `traefik/dynamic.yml` (file-cert TLS)

## Quick start (existing certificates)

1) Create your env file:

```bash
cp .env.example .env
```

Edit `.env` and set at least:
- `APP_HOSTNAME` (your existing domain, ex: `audela.example.com`)
- `GRAFANA_HOSTNAME` (ex: `grafana.example.com`)
- `SECRET_KEY` and `DATA_KEY`
- `POSTGRES_*` and `GRAFANA_ADMIN_PASSWORD`

2) Put your TLS certs here:

```
./certs/fullchain.pem
./certs/privkey.pem
```

3) Start:

```bash
docker compose up -d --build
```

### Result

- App: `https://$APP_HOSTNAME/`
- Login: `https://$APP_HOSTNAME/app/login`
- Grafana: `https://$GRAFANA_HOSTNAME/` (admin creds from `.env`)

Ports exposed on the host: **80** and **443** (Traefik). Everything else stays private.

## Alternative: Let's Encrypt certificates

If you prefer auto-managed TLS:

```bash
cp .env.example .env
# set APP_HOSTNAME, GRAFANA_HOSTNAME, LETSENCRYPT_EMAIL, secrets...

docker compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d --build
```

Notes:
- HTTP-01 challenge requires public access to port **80** for the hostnames you set.
- Certificates are stored in a volume (`traefik_letsencrypt`).

## Data persistence

Volumes created:
- `postgres_data` (PostgreSQL)
- `redis_data` (Redis)
- `audela_instance` (`/app/instance` → SQLite fallback, uploads, tenant files)
- `prometheus_data`, `grafana_data`

## How to keep *exactly* the same public behaviour

- Keep your current DNS name for the app and set it in `APP_HOSTNAME`.
- Keep ports **80/443** on the host (already the default in `docker-compose.yml`).
- If you already have certificates, copy them into `./certs/` (same filenames).

If your previous install exposed additional ports (ex: 5000), you can still map them, but the recommended production setup is **only 80/443**.
