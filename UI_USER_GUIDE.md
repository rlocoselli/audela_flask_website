# Guide Complet - Interface Utilisateur Finance

**Date:** Février 2026  
**Version:** 1.0  
**Statut:** ✅ Complete

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Dashboard Principal](#dashboard-principal)
3. [Gestion des Produits](#gestion-des-produits)
4. [Gestion des Contreparties](#gestion-des-contreparties)
5. [Configuration Bancaire](#configuration-bancaire)
6. [Access & Permissions](#access--permissions)

---

## Vue d'Ensemble

Les interfaces utilisateur permettent aux utilisateurs de gérer complètement leurs données financières dans un contexte **multi-tenant**:

- ✅ **Isolation tenant:** Chaque utilisateur ne voit que ses données
- ✅ **CRUD complet:** Créer, lire, mettre à jour, supprimer
- ✅ **Validation automatique:** IBAN, emails, etc.
- ✅ **Responsive:** Mobile-friendly Bootstrap 5
- ✅ **Recherche & pagination:** Performance optimisée

### URL Base
```
/finance/master/
```

### Flux d'Accès
```
1. Authentification → 2. Tenant chargé → 3. Accès aux UIs
```

---

## Dashboard Principal

**URL:** `/finance/master`  
**Method:** GET  
**Auth:** Login required

### Fonctionnalités

- **Accès rapide** aux 3 sections principales
- **Statistiques instantanées:**
  - Nombre de produits
  - Nombre de contreparties
  - Statut IBAN compagnie
  - Statut synchronisation bancaire
- **Guide rapide** pour nouveaux utilisateurs
- **Conseils** et bonnes pratiques

### Écran

```
┌─────────────────────────────────────────┐
│ Gestion Financière                      │
│                                         │
│ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│ │ Produits │ │Contreparties│ │Banque    │ │
│ │   📦     │ │  👥     │ │🏦      │ │
│ │  Voir    │ │ Voir    │ │ Configurer
│ │ Créer    │ │ Créer   │ │        │ │
│ └──────────┘ └──────────┘ └─────────┘ │
│                                         │
│ Statistiques: 15 produits | 42 contreparties...
└─────────────────────────────────────────┘
```

---

## Gestion des Produits

### 1. Lister les Produits

**URL:** `/finance/master/products`  
**Method:** GET  
**Template:** `finance/products/list.html`

#### Fonctionnalités
- 📊 Tableau paginé (20 par page)
- 🔍 Recherche par nom ou code
- 📌 Badge TVA (montante taux ou "Exempté")
- ✏️ Édition en ligne
- 🗑️ Suppression avec confirmation

#### Exemple

```
Produits Financiers

[Rechercher...] [Chercher]

┌─────────────────────────────────────────────┐
│ Nom        │ Code  │ Description │ TVA │Actions
├─────────────────────────────────────────────┤
│ Consulting │ CONS-001 │ Service de conseil │ 20% │ Éditer | Supprimer
│ Dev        │ DEV-014  │ Développement logiciel 20% │ Éditer | Supprimer
│ ...        │ ...   │ ...        │ ... │ ...
└─────────────────────────────────────────────┘

Pagination: 1 2 3 [4] 5 ...
```

### 2. Créer un Produit

**URL:** `/finance/master/products/create`  
**Method:** GET, POST  
**Template:** `finance/products/create.html`

#### Formulaire

**Section: Informations Générales**
- `name` (required): Nom du produit
- `code` (optional): Code interne unique
- `description` (optional): Description détaillée

**Section: Configuration TVA**
- `vat_applies` (checkbox): Le produit est soumis à la TVA?
  - Si OUI → affiche champ `vat_rate`
  - Si NON → affiche champ `tax_exempt_reason`
- `vat_rate` (number): Taux TVA en % (0-100)
- `tax_exempt_reason` (text): Motif de l'exonération

#### Exemple de Route

```python
POST /finance/master/products/create
Content-Type: application/x-www-form-urlencoded

name=Consulting&code=CONS-001&description=Service de conseil...&vat_applies=on&vat_rate=20.0

Response →
201 Created
Location: /finance/master/products?company_id=1
Message: "Produit créé avec succès"
```

### 3. Éditer un Produit

**URL:** `/finance/master/products/<product_id>/edit`  
**Method:** GET, POST  
**Template:** `finance/products/edit.html`

#### Changements Importants
- ⚠️ Le `code` est en **lecture seule** (immuable)
- ✏️ Les autres champs sont éditables
- ⚠️ Les modifications n'affectent que les futurs transactions

#### Exemple

```python
POST /finance/master/products/42/edit
Content-Type: application/x-www-form-urlencoded

name=Consulting Updated&description=Updated description...&vat_applies=on&vat_rate=20.0

Response →
302 Redirect
Location: /finance/master/products?company_id=1
Message: "Produit mis à jour"
```

### 4. Supprimer un Produit

**URL:** `/finance/master/products/<product_id>/delete`  
**Method:** POST  
**Confirmation:** Client-side JavaScript

#### Exemple

```python
POST /finance/master/products/42/delete

Response →
302 Redirect
Location: /finance/master/products?company_id=1
Message: "Produit supprimé"
```

---

## Gestion des Contreparties

### 1. Lister les Contreparties

**URL:** `/finance/master/counterparties`  
**Method:** GET  
**Template:** `finance/counterparties/list.html`

#### Fonctionnalités
- 📊 Tableau avec infos bancaires
- 🔍 Recherche multi-champs (nom, SIRET, IBAN)
- 📧 Liens email/téléphone directs
- 🌍 Code pays affiché
- ✏️ Édition complète
- 🗑️ Suppression sécurisée

#### Colonnes

| Colonne | Contenu |
|---------|---------|
| Nom | Nom complet + code pays |
| Identifiant | SIRET/SIREN en code |
| IBAN | IBAN + BIC si disponible |
| Contact | Email + téléphone |
| Actions | Éditer / Supprimer |

### 2. Créer une Contrepartie

**URL:** `/finance/master/counterparties/create`  
**Method:** GET, POST  
**Template:** `finance/counterparties/create.html`

#### Formulaire Multi-Sections

**Section 1: Informations Générales**
- `name*` (required): Nom complet
- `tax_id`: SIRET/SIREN
- `country_code`: Code pays ISO (FR, DE, IT, etc.)
- `address`: Adresse complète

**Section 2: Informations Bancaires**
- `iban`: IBAN validé en tempo réel (ISO 13616)
- `bic`: Code SWIFT

**Section 3: Coordonnées**
- `email`: Email validé
- `phone`: Numéro de téléphone

#### Validation IBAN en Temps Réel

```javascript
// Lors du changement de l'input IBAN
POST /finance/master/api/validate-iban
Content-Type: application/json

{ "iban": "FR1420041010050500013M02606" }

Response:
{
  "valid": true,
  "message": "Valid IBAN",
  "formatted": "FR14 2004 1010 0505 0001 3M02 606"
}
```

#### Exemple complet

```python
POST /finance/master/counterparties/create
Content-Type: application/x-www-form-urlencoded

name=ABC SA
tax_id=12345678901234
iban=FR1420041010050500013M02606
bic=SOCFRPP
email=contact@abc.fr
phone=+33123456789
address=123 Avenue de France, 75000 PARIS
country_code=FR

Response →
302 Redirect
Location: /finance/master/counterparties?company_id=1
Message: "Contrepartie créée"
```

### 3. Éditer une Contrepartie

**URL:** `/finance/master/counterparties/<counterparty_id>/edit`  
**Method:** GET, POST  
**Template:** `finance/counterparties/edit.html`

#### Caractéristiques
- ✏️ Tous les champs éditables
- ✅ Validation IBAN à nouveau
- 📅 Horodatage création/modification affiché
- ⚖️ Historique des modifications (logs)

### 4. Supprimer une Contrepartie

**URL:** `/finance/master/counterparties/<counterparty_id>/delete`  
**Method:** POST

```python
POST /finance/master/counterparties/42/delete

Response →
302 Redirect
Location: /finance/master/counterparties
Message: "Contrepartie supprimée"
```

---

## Configuration Bancaire

### URL

**URL:** `/finance/master/bank-config`  
**Method:** GET, POST  
**Template:** `finance/bank_config.html`

### Sections

#### 1. Configuration IBAN (Gauche)

**Fonctionnalités:**
- ✅ Affiche IBAN actuel si configuré
- ✨ Validation ISO 13616 en temps réel
- 📝 Formatage automatique (FR14 2004 1010...)
- 🔄 Modification à tout moment

**Formulaire:**
```html
<input type="text" name="iban" placeholder="FR1420041010050500013M02606" required>
<button type="submit">Configurer IBAN</button>
```

**API Validation:**
```python
POST /finance/master/api/validate-iban

# Requête
{
  "iban": "FR1420041010050500013M02606"
}

# Réponse
{
  "valid": true,
  "message": "Valid IBAN",
  "formatted": "FR14 2004 1010 0505 0001 3M02 606"
}
```

#### 2. Synchronisation Bancaire (Droite)

**GoCardless/Nordigen Integration**
- 🔐 Connexion sécurisée PSD2
- ⚡ Import temps réel des transactions
- 🏦 Support multi-banques
- 📊 Synchronisation automatique

**Bouton de Connexion:**
```
[Connecter une Banque]
```

Clique lance OAuth flow GoCardless.

#### 3. Comptes Bancaires Associés

**Vue d'ensemble:**
- Configuration IBAN par compagnie
- IBAN par compte financier
- IBAN par contrepartie

**Liens Utiles:**
- → Aller à la liste des Comptes
- → Aller à la Gestion des Contreparties

---

## Access & Permissions

### Contrôle d'Accès

**Authentification:**
```python
@login_required
def routes(...)
```
- ✅ Utilisateur doit être connecté
- ✅ Session valide
- ❌ Sinon → redirect vers login

**Autorisation Tenant:**
```python
def _require_tenant():
    if not current_user.is_authenticated:
        abort(401)
    if current_user.tenant_id != g.tenant.id:
        abort(403)  # Forbidden
```
- ✅ Utilisateur doit appartenir au tenant
- ❌ Sinon → 403 Forbidden

**Sélection Compagnie:**
- Utilisateur sélectionne compagnie via session
- Requête via GET param `?company_id=1`
- Validation: compagnie doit appartenir au tenant

### Flux Complet

```
1. User accède /finance/master/products
   ↓
2. @login_required check → Authentifié? OUI ✓
   ↓
3. _require_tenant() → Appartient au tenant? OUI ✓
   ↓
4. _get_company() → Compagnie du tenant? OUI ✓
   ↓
5. Afficher template avec données filtrées
```

---

## URL Résumé

| Page | URL | Method | Auth |
|------|-----|--------|------|
| Dashboard | `/finance/master` | GET | Login |
| Produits (Liste) | `/finance/master/products` | GET | Login |
| Produit (Créer) | `/finance/master/products/create` | GET, POST | Login |
| Produit (Éditer) | `/finance/master/products/<id>/edit` | GET, POST | Login |
| Produit (Supprimer) | `/finance/master/products/<id>/delete` | POST | Login |
| Contreparties (Liste) | `/finance/master/counterparties` | GET | Login |
| Contrepartie (Créer) | `/finance/master/counterparties/create` | GET, POST | Login |
| Contrepartie (Éditer) | `/finance/master/counterparties/<id>/edit` | GET, POST | Login |
| Contrepartie (Supprimer) | `/finance/master/counterparties/<id>/delete` | POST | Login |
| Config Bancaire | `/finance/master/bank-config` | GET, POST | Login |
| API: Valider IBAN | `/finance/master/api/validate-iban` | POST | Login |

---

## Exemples de Workflows

### Workflow 1: Ajouter un Client

```
1. Accéder à /finance/master/counterparties
2. Cliquer "Nouvelle Contrepartie"
3. Remplir formulaire:
   - Nom: "ACME Corp"
   - SIRET: "12345678901234"
   - IBAN: "FR1420041010050500013M02606" (validé auto)
   - Email/Tél: ...
4. Soumettre
5. Voir dans liste avec recherche possible
```

### Workflow 2: Configurer l'IBAN de Compagnie

```
1. Accéder à /finance/master/bank-config
2. Section "Configuration IBAN"
3. Entrer: "FR1420041010050500013M02606"
   → Validation en temps réel: ✓ Valide
4. Cliquer "Configurer IBAN"
5. Message: "IBAN configuré avec succès"
6. IBAN s'affiche formaté
```

### Workflow 3: Gérer Produits avec TVA

```
1. Accéder à /finance/master/products
2. Cliquer "Nouveau Produit"
3. Nom: "Consulting"
4. Code: "CONS-001"
5. TVA:
   - Checkbox "Soumis à TVA" → OUI
   - Taux: 20.0
6. Créer
7. Consulter dans liste
```

---

## Intégration dans la Navigation

Les UIs doivent être accessibles depuis le menu principal:

```html
<!-- Menu Finance -->
<a href="/finance/master">Gestion Finance</a>
  ├─ <a href="/finance/master/products">Produits</a>
  ├─ <a href="/finance/master/counterparties">Contreparties</a>
  └─ <a href="/finance/master/bank-config">Config Bancaire</a>
```

---

## Support & Troubleshooting

### Erreur: "IBAN invalide"

**Cause possible:**
- Mauvais pays (ex: DE au lieu de FR)
- Checksum incorrect
- Format invalide

**Solution:**
- Copier l'IBAN depuis relevé bancaire
- Vérifier 2 premières lettres = code pays
- Essayer validation en ligne: https://www.iban.com/validator

### Erreur: "Contrepartie non trouvée"

**Cause possible:**
- Tentative accès autre tenant
- ID invalide

**Solution:**
- Rafraîchir la page
- Revenir à la liste
- Vérifier permissions

### Pertes de Données

**Sécurité:**
- ✅ Confirmation avant suppression
- ✅ Soft-delete possible (TODO)
- ✅ Audit logs des modifications(TODO)

---

**Version:** 1.0  
**Dernière mise à jour:** Février 2026  
**Auteur:** Finance Team
