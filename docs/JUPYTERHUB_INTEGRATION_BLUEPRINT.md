# JupyterHub Integration Blueprint for ML Studio

This ML Studio uses Jupyter as the interactive experimentation layer, not as the full platform.

## Architecture

- ML Studio remains the product surface for governance, model lifecycle, deployment and monitoring.
- JupyterHub/JupyterLab is the experimentation layer per user/project.
- Heavy training should be delegated to remote kernels/jobs (Kubernetes/GPU pods) and tracked in MLflow.

## Implemented foundation in this repository

- Project-scoped notebook workspace scaffolding under tenant files.
- JupyterHub URL support via `JUPYTERHUB_BASE_URL`.
- Curated notebook model builders with required parameter validation.
- Notebook registration bridge to ML Studio model registry.
- CI smoke checks for notebook and Jupyter integration contract.

## Environment variables

- `JUPYTERHUB_BASE_URL`:
  - Example with placeholder: `https://jupyterhub.example.com/user/{username}`
  - Example base URL: `https://jupyterhub.example.com`
- `JUPYTER_SUPPORTED_KERNELS`:
  - Comma-separated list, e.g. `python,r,sql,scala`
- `JUPYTER_PREBUILT_ENVS`:
  - Comma-separated list, e.g. `sklearn,pytorch,tensorflow,xgboost,huggingface`
- Existing local embed fallback:
  - `JUPYTER_EMBED_URL`
  - `JUPYTER_EMBED_TOKEN`

## Tenant and project isolation

- Local Jupyter launcher requires `AUDELA_TENANT_ID` and uses:
  - `instance/tenant_files/<tenant_id>/notebooks` (strict tenant root)
- Per-project workspace scaffolding uses:
  - `instance/tenant_files/<tenant_id>/projects/<project_slug>/...`

## Workspace scaffold

For each project:

- `notebooks/`
- `src/`
- `data/`
- `models/`
- `pipelines/`
- `requirements.txt`
- `environment.yml`
- `Dockerfile`
- `mlstudio.yaml`

## Next recommended steps

- Add JupyterLab extension for ML Studio sidebar (datasets, experiments, models, pipelines, deployments).
- Connect Enterprise Gateway for remote kernels and Kubernetes job execution.
- Add notebook-to-pipeline conversion and deploy-as-API commands.
- Add resource/cost telemetry widgets and run-level governance controls.
