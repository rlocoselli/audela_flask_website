# AUDELA Platform

A multi-product data platform built with Flask, focused on analytics, finance workflows, project operations, and learning experiences.

## ✨ What You Get

- 🧠 BI workspace with SQL editor, saved questions, dashboards, and AI-assisted analysis
- 💼 Finance workspace for accounting flows, statement import, and ratio insights
- 📊 Project workspace for planning, tracking, and delivery monitoring
- 🤖 ML workspace with MLflow integration and notebook-ready foundations
- 🎓 E-learning academy with multi-subject modules, quizzes, and interactive math labs
- 🏢 Tenant-aware architecture with role-based access and scoped data operations

## 🧱 Tech Stack

- **Backend**: Flask, SQLAlchemy, Alembic
- **Async**: Celery + Redis
- **DB**: PostgreSQL (production), SQLite fallback (local)
- **Infra**: Docker Compose, Traefik, Prometheus, Grafana
- **AI Providers**: OpenAI and Mistral (switchable per tenant)

## 🚀 Quick Start (Local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app2.py
```

Open:

- `http://127.0.0.1:5000/` (public pages)
- `http://127.0.0.1:5000/e-learning/` (academy)
- `http://127.0.0.1:5000/tenant/login` (tenant access)

## 🔐 AI Provider Configuration

AUDELA supports runtime switching between OpenAI and Mistral.

Server environment keys:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional)
- `OPENAI_BASE_URL` (optional)
- `MISTRAL_API_KEY`
- `MISTRAL_MODEL` (optional, default `mistral-small-latest`)
- `MISTRAL_BASE_URL` (optional, default `https://api.mistral.ai/v1`)

Tenant-level switch:

- Go to `Tenant > Profile > AI Configuration`
- Select provider (`OpenAI` or `Mistral AI`)
- Optionally override model

## 🐳 Docker Deployment

For production-style deployment (TLS, monitoring, MLflow, Celery):

- Read: `README_DOCKER.md`

Main deployment workflow:

- `.github/workflows/deploy.yml`

## 📚 Key Project Files

- `app2.py`: app entrypoint used in local runs
- `audela/config.py`: runtime settings and environment mapping
- `audela/services/ai_runtime_config.py`: provider resolution (OpenAI/Mistral)
- `templates/e_learning/lesson_view.html`: finance + Cartesian interactive graph labs

## 🧪 Validation Commands

```bash
python -m py_compile audela/services/ai_service.py audela/services/openai_statement.py
python app2.py
```

## 🛣️ Suggested Next Improvements

- Add pytest coverage for provider switching and AI fallback paths
- Add visual regression checks for e-learning interactive graph components
- Add smoke tests for tenant AI provider changes across products

## 📄 License

See `LICENSE.txt`.
