# AUDELA Flask Website + BI Portal (MVP scaffold)

This repo keeps the public marketing pages and adds a logged `/app` area as the starting point of your multi-tenant BI solution.

## MVP features implemented

- **Cadastro de fontes de dados por tenant** (config criptografada)
- **Explorador de metadados** (introspecção via SQLAlchemy inspector)
- **Editor SQL** (execução ad-hoc read-only com limites)
- **Perguntas** (queries salvas) + execução (QueryRun)
- **Dashboards** (cards simples baseados em perguntas)
- **Auditoria** (AuditEvent) e **logs** (QueryRun) por tenant

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=app.py
export FLASK_ENV=development

# Dev default: AUTO_CREATE_DB=true (cria as tabelas automaticamente no SQLite)
python app.py
```

Open:
- Public site: `http://localhost:5000/`
- Login: `http://localhost:5000/app/login`
- Bootstrap (dev only): `http://localhost:5000/app/bootstrap`

After bootstrapping and logging in:
- Fontes: `/app/sources`
- Editor SQL: `/app/sql`
- Perguntas: `/app/questions`
- Dashboards: `/app/dashboards`
- Auditoria: `/app/audit`
- Execuções: `/app/runs`

## Tenancy model

MVP uses **model 1** (shared app DB with `tenant_id` on all BI entities) and **enforces scoping in backend**. Production hardening should add:
- normalized ACL tables (instead of JSON)
- tenant-aware query services and tests
- database constraints and/or RLS for shared data sources

## Notes

- To use **PostgreSQL** for the app DB, set `DATABASE_URL` (e.g. `postgresql+psycopg://...`) and run `flask db upgrade`.
- `DATA_KEY` can be set to rotate the encryption key used for datasource configs (otherwise it derives from `SECRET_KEY` in dev).

