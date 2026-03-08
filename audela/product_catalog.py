"""Central product catalog used by public and tenant product pages."""

from __future__ import annotations

from typing import Any


PRODUCT_CATALOG: dict[str, dict[str, Any]] = {
    "finance": {
        "public_title": "Produit Finance",
        "meta_description": "Solution Finance française pour pilotage de trésorerie, cashflow, conformité et auditabilité. Une plateforme claire pour directions financières, PME et cabinets comptables.",
        "subtitle": "Pilotage financier, trésorerie et conformité, dans une plateforme unique.",
        "overview": "La plateforme Finance centralise la trésorerie, la conformité et le pilotage de performance pour les équipes financières qui doivent décider vite.",
        "image": "images/audela-carousel-03.svg",
        "image_alt": "Image du produit Finance",
        "features": [
            "Cash management multi-comptes et vision de liquidité en temps réel.",
            "Rapprochement bancaire assisté et catégorisation automatique.",
            "Prévisions glissantes, scénarios et alertes sur seuils critiques.",
            "Exports réglementaires, piste d'audit et journal des actions.",
        ],
        "integrations": [
            "Connecteurs bancaires Powens/Tink, import CSV/Excel et API REST.",
            "Déploiement cloud sécurisé, gestion multi-tenant et droits par profil.",
            "Historisation complète pour audit interne et conformité externe.",
        ],
        "use_cases": [
            "Suivi quotidien de trésorerie pour PME et ETI.",
            "Consolidation multi-entités pour groupes et holdings.",
            "Pilotage de conformité pour directions financières et cabinets.",
        ],
        "outcomes": [
            "Réduction du temps de clôture et meilleure qualité des données.",
            "Décisions plus rapides grâce à une vision consolidée.",
            "Moins de tâches manuelles et davantage de contrôle.",
        ],
        "audience": "Directions financières, cabinets comptables, PME et groupes multi-entités.",
        "plans_cta": "Découvrir les plans Finance",
        "plans_slug": "finance",
        "tenant_title": "AUDELA Finance",
        "tenant_summary": "Gestion financière complète avec synchronisation bancaire, calcul LCR/NSFR, et rapports réglementaires.",
        "tenant_access_label": "Accéder à Finance",
        "tenant_access_disabled": "Accès Finance désactivé",
    },
    "bi": {
        "public_title": "Produit BI",
        "meta_description": "Plateforme BI française pour analyse de données, tableaux de bord et gouvernance data. Connectez vos sources SQL/API et pilotez vos décisions métier avec confiance.",
        "subtitle": "Décision pilotée par la donnée, de la source au dashboard.",
        "overview": "AUDELA BI transforme vos données en décisions opérationnelles avec des tableaux de bord actionnables, une gouvernance claire et une supervision continue.",
        "image": "images/audela-carousel-01.svg",
        "image_alt": "Image du produit BI",
        "features": [
            "Connexion aux sources SQL/API et gouvernance par tenant.",
            "Modélisation, requêtes, visualisations et dashboards.",
            "Partage sécurisé, exports et supervision des exécutions.",
            "Assistant IA pour accélérer l'analyse.",
        ],
        "integrations": [
            "Connexion aux bases SQL, APIs et fichiers métier.",
            "Gestion des espaces par tenant avec permissions granulaires.",
            "Déploiement progressif et supervision des requêtes critiques.",
        ],
        "use_cases": [
            "Suivi ventes, marge et performance commerciale multi-segments.",
            "Analyse des opérations, délais et goulots d'étranglement.",
            "Pilotage exécutif avec KPI consolidés en temps réel.",
        ],
        "outcomes": [
            "Cycle de décision plus court grâce à des KPI fiables.",
            "Autonomie des équipes métier sur l'analyse quotidienne.",
            "Meilleure gouvernance de la donnée sur toute la chaîne BI.",
        ],
        "audience": "Équipes data, opérations, direction générale et métiers.",
        "plans_cta": "Découvrir les plans BI",
        "plans_slug": "bi",
        "tenant_title": "AUDELA BI",
        "tenant_summary": "Business Intelligence avec tableaux de bord interactifs, analyses avancées et requêtes SQL personnalisées.",
        "tenant_access_label": "Accéder à BI",
        "tenant_access_disabled": "Accès BI désactivé",
    },
    "credit": {
        "public_title": "Produit Audela Credit",
        "meta_description": "Solution Audela Credit pour l origination bancaire: borrowers, deals, facilities, collateraux, garants, ratios, credit memo et workflow d approbation.",
        "subtitle": "Origination de credit pour petites banques, de l analyse au comite de decision.",
        "overview": "Audela Credit structure l'origination bancaire de bout en bout, avec un parcours clair depuis la saisie du deal jusqu'à la décision finale.",
        "image": "images/audela-carousel-02.svg",
        "image_alt": "Image du produit Audela Credit",
        "features": [
            "Gestion des borrowers, deals, facilities et collatéraux.",
            "Gestion des garants, documents, memos et workflow d'approbation.",
            "Spreading des états financiers et snapshots de ratios de risque.",
            "Reporting dédié pour comités de crédit et suivi des SLA.",
        ],
        "integrations": [
            "Paramétrage des workflows d'approbation et des matrices de délégation.",
            "Connexion aux sources financières pour importer les états et ratios.",
            "Traçabilité complète des décisions et des documents de crédit.",
        ],
        "use_cases": [
            "Origination retail et PME avec standardisation des dossiers.",
            "Processus comité avec validation multi-niveaux.",
            "Suivi du portefeuille avec alertes de risque et retard.",
        ],
        "outcomes": [
            "Décisions de crédit plus rapides et mieux documentées.",
            "Réduction des risques opérationnels et réglementaires.",
            "Visibilité consolidée pour analystes, risque et comité.",
        ],
        "audience": "Analystes crédit, risk managers et comités de crédit des banques de proximité.",
        "plans_cta": "Découvrir les plans Audela Credit",
        "plans_slug": "credit",
        "tenant_title": "Audela Credit",
        "tenant_summary": "Origination de crédit pour petites banques avec borrowers, deals, facilities, collatéraux, garants, spreading, ratios, credit memo et workflow d’approbation.",
        "tenant_access_label": "Accéder à Audela Credit",
        "tenant_access_disabled": "Accès Audela Credit désactivé",
    },
    "project": {
        "public_title": "Produit Projet",
        "meta_description": "Outil de pilotage projet français pour PMO, DSI et équipes delivery : portefeuille, planning, risques, reporting et gouvernance opérationnelle en temps réel.",
        "subtitle": "Pilotage de projets, PMO et exécution terrain en temps réel.",
        "overview": "AUDELA Projet aide à planifier, prioriser et exécuter les initiatives avec une vision commune entre PMO, métiers et équipes delivery.",
        "image": "images/audela-carousel-04.svg",
        "image_alt": "Image du produit Projet",
        "features": [
            "Vue portefeuille, planning, risques et dépendances.",
            "Kanban, Gantt et suivi d'avancement par responsable.",
            "Gestion des décisions, changements et incidents.",
            "Reporting consolidé pour gouvernance et comités.",
        ],
        "integrations": [
            "Structuration par programme, projet, lot et livrable.",
            "Gestion des rôles, responsables et niveaux de priorité.",
            "Export des suivis pour comités de pilotage et direction.",
        ],
        "use_cases": [
            "Pilotage de portefeuille IT et transformation digitale.",
            "Coordination multi-équipes sur projets transverses.",
            "Suivi des jalons, risques et arbitrages en comité.",
        ],
        "outcomes": [
            "Meilleure visibilité sur les priorités et dépendances.",
            "Exécution plus fluide grâce à un pilotage partagé.",
            "Réduction des retards et meilleure maîtrise des risques.",
        ],
        "audience": "PMO, chefs de projet, DSI et équipes de delivery.",
        "plans_cta": "Découvrir les plans Projet",
        "plans_slug": "project",
        "tenant_title": "AUDELA Project",
        "tenant_summary": "Pilotage projet simple avec tableau Kanban, timeline Gantt, arbre des livrables et cérémonies Agile/Scrum.",
        "tenant_access_label": "Accéder à Projet",
        "tenant_access_disabled": "Accès Projet désactivé",
    },
}


def get_product_catalog() -> dict[str, dict[str, Any]]:
    return PRODUCT_CATALOG


def get_product_entry(product_key: str) -> dict[str, Any]:
    return PRODUCT_CATALOG[product_key]
