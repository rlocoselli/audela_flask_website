# Audit i18n — 2026-02-22

## Résumé exécutif

L’application est globalement internationalisée sur les parcours principaux, mais il reste des **zones non homogènes** qui provoquent des textes figés (FR/EN/PT) selon l’écran et le module.

### Causes racine identifiées

1. **Doublon de templates Finance** dans deux arbres:
   - `templates/finance/*`
   - `audela/templates/finance/*`
   
   Une correction peut être faite dans un arbre sans impacter l’autre.

2. **Chaînes hardcodées dans templates/JS** (notamment dans écrans master data et modales JS).

3. **Messages backend non passés par `tr()`** dans certains blueprints/services (`flash`, erreurs, `ValueError`).

4. **Clés de traduction hétérogènes** (mélange FR/PT/EN comme msgid, orthographes variées), ce qui complexifie la couverture complète.

---

## Correctifs appliqués immédiatement

### Backend
- `audela/tenancy.py`
  - Messages de garde tenant (`flash`) passés par `tr()`.
- `audela/blueprints/public/routes.py`
  - Messages de formulaire démo (`flash`) passés par `tr()`.

### Frontend
- `templates/finance/investments_list.html`
  - Chaînes JS hardcodées (historique/performance) remplacées par chaînes i18n via `{{ _('...') }}`.

### Dictionnaire
- `audela/i18n.py`
  - Ajout d’un bloc `_I18N_HOTFIX_20260222` pour couvrir les nouveaux msgid critiques.

---

## Zones avec dette i18n (priorité haute)

## 1) Master Data Finance (non traduit à grande échelle)
- `templates/finance/master_dashboard.html`
- `templates/finance/products/*.html`
- `templates/finance/counterparties/*.html`
- `templates/finance/bank_config.html`
- et leurs doublons `audela/templates/finance/...`

Constat: nombreux libellés FR en dur hors `{{ _('...') }}`.

## 2) Messages backend en anglais/français hors `tr()`
Exemples repérés:
- `audela/blueprints/billing/routes.py` (plusieurs `flash("...")`)
- `audela/services/tenant_service.py` (plusieurs `ValueError("...")`)
- `audela/services/subscription_service.py` (messages EN)

## 3) Incohérences de clés
Exemples:
- clés mélangées FR/PT/EN pour des concepts identiques;
- variantes orthographiques dans certains msgid (risque de “clé manquante”).

---

## Plan de remédiation recommandé

## Lot A (rapide, impact UI fort)
1. Unifier source de vérité templates finance (préférer `templates/finance`).
2. Migrer tous textes visibles Master Data vers `{{ _('...') }}`.
3. Conserver compatibilité via `i18n` hotfix le temps de stabiliser.

## Lot B (backend)
1. Standardiser `flash(tr(...))` partout.
2. Remplacer les `ValueError` utilisateur par messages traduisibles (ou codes d’erreur + mapping).

## Lot C (qualité continue)
1. Ajouter script de lint i18n (détection de textes en dur dans templates + `flash("...")` non traduits).
2. Bloquer en CI (warning puis erreur) sur nouveaux textes hardcodés.

---

## Recommandation architecture i18n

- Garder `msgid` dans une langue pivot unique (ex: français ou anglais), pas un mélange.
- Éviter d’introduire de nouvelles clés ad hoc avec variantes typographiques.
- Ajouter une convention: toute chaîne visible utilisateur = `tr()` / `_()`.

---

## État actuel après ce passage

- Les écrans récemment modifiés (navigation mobile + actions responsive + historique investissements) sont plus propres côté i18n.
- Les points de friction principaux restants se concentrent dans les écrans master data et certains messages backend non harmonisés.

---

## Mise à jour Lot B (backend) — réalisé

- `audela/blueprints/billing/routes.py`
  - Tous les `flash(...)` utilisateur passent désormais par `tr(..., lang)`.
- `audela/blueprints/tenant/routes.py`
  - Erreurs `ValueError` upload harmonisées (clés traduisibles).
- `audela/i18n.py`
  - Extension du bloc hotfix avec les clés billing/tenant restantes (`Admin access required`, `Invitation sent to {email}`, etc.).

### Effet

- Diminution forte des messages anglais/français bruts côté portail tenant/billing.
- Meilleure cohérence multi-langue sans changer le comportement métier.

