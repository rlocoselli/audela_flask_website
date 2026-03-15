# Open Banking + GitHub Actions (Bridge / Powens)

Ce guide explique:
- quels secrets GitHub configurer
- ou recuperer/generer les codes
- quelles URLs utiliser
- comment verifier que tout fonctionne apres deploy

## 1. Secrets GitHub a configurer

Dans GitHub:
- `Settings` -> `Environments` -> `audeladesdonnees` -> `Secrets`

Ajouter ces secrets:
- `BRIDGE_CLIENT_ID`
- `BRIDGE_CLIENT_SECRET`
- `POWENS_CLIENT_ID` (optionnel)
- `POWENS_CLIENT_SECRET` (optionnel)
- `POWENS_WEBHOOK_SECRET` (optionnel)
- `ENCRYPTION_KEY` (recommande si tokens sensibles)

Deja utilises aussi par le deploy:
- `SERVER_ENV_FILE` (optionnel, bootstrap complet du `.env`)
- `GRAFANA_HOSTNAME`
- `GRAFANA_HOSTNAME_ALT`

Dans GitHub `Environment variables` (non secrets):
- `BRIDGE_BASE_URL` (ex: `https://api.bridgeapi.io`)
- `BRIDGE_VERSION` (ex: `2025-01-15`)

## 2. Ou recuperer les credentials

## Bridge (Open Banking principal dans ce projet)
- Site: `https://bridgeapi.io`
- Docs: `https://docs.bridgeapi.io/docs/quickstart`
- API reference: `https://docs.bridgeapi.io/reference/`

Etapes:
1. Creer/activer votre compte Bridge.
2. Creer une application API.
3. Recuperer `client_id` et `client_secret`.
4. Placer ces valeurs dans les secrets GitHub:
   - `BRIDGE_CLIENT_ID`
   - `BRIDGE_CLIENT_SECRET`

## Powens (optionnel)
- Developers: `https://powens.com/developers`
- Console signup: `https://console.powens.com/auth/register`
- Docs: `https://docs.powens.com/documentation/`

Etapes:
1. Creer un compte console.
2. Lancer un sandbox si besoin.
3. Recuperer les API keys.
4. Placer les valeurs dans:
   - `POWENS_CLIENT_ID`
   - `POWENS_CLIENT_SECRET`
   - `POWENS_WEBHOOK_SECRET` (si webhook)

## 3. Generer ENCRYPTION_KEY

Si vous stockez des tokens/API secrets en base, generer une cle de chiffrement.

Exemple Python (Fernet):

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

Ajouter la valeur dans le secret GitHub:
- `ENCRYPTION_KEY`

## 4. URLs a configurer

## Callback Bridge
La route applicative est:
- `/finance/banks/callback`

URL complete en production:
- `https://audeladedonnees.fr/finance/banks/callback`

Utilisez ce domaine dans la config Bridge (allowed domain / callback policy selon votre plan).

Optionnel (si vous voulez forcer cette valeur dans l'app):
- GitHub Environment variable `BRIDGE_CALLBACK_URL = https://audeladedonnees.fr/finance/banks/callback`

## Webhook Powens (si active)
URL proposee:
- `https://<votre-domaine>/webhooks/powens`

Note: ce webhook est documente dans le repo, mais l integration Powens dans le code actuel est surtout en mode stub.

## 5. Ce que fait maintenant le workflow deploy

Le workflow `.github/workflows/deploy.yml`:
- lit les secrets GitHub Environment
- passe les variables au serveur SSH
- met a jour/insere automatiquement ces cles dans `.env`:
   - `SITE_URL`
   - `BRIDGE_CALLBACK_URL`
  - `BRIDGE_CLIENT_ID`
  - `BRIDGE_CLIENT_SECRET`
  - `BRIDGE_BASE_URL`
  - `BRIDGE_VERSION`
  - `POWENS_CLIENT_ID`
  - `POWENS_CLIENT_SECRET`
  - `POWENS_WEBHOOK_SECRET`
  - `ENCRYPTION_KEY`

## 6. Verification apres deploy

1. Lancer le workflow `Deploy Flask App (root)`.
2. Ouvrir l app: `Finance` -> `Banks` (`/finance/banks`).
3. Verifier que le message "API bancaria nao configurada" n apparait plus.
4. Cliquer `Conectar banco`.
5. Verifier retour sur callback puis lancer `Sync`.

## 7. Checklist rapide

- [ ] Secrets ajoutes dans GitHub Environment `audeladesdonnees`
- [ ] Variables `BRIDGE_BASE_URL` et `BRIDGE_VERSION` ajoutees
- [ ] Variables `SITE_URL` et `BRIDGE_CALLBACK_URL` verifiees
- [ ] Callback URL production confirmee: `/finance/banks/callback`
- [ ] Deploy execute
- [ ] Connexion bancaire testee depuis `/finance/banks`

## 8. Migration GitHub Action

Le workflow `migrations-only.yml` applique maintenant `flask db upgrade heads` (multi-head Alembic) et pre-stamp `20260315_add_finance_quotes_tables` si les tables existent deja.
