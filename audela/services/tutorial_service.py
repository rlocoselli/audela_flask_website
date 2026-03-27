"""Tutorial configuration and management service.

This service provides comprehensive tutorial configurations for all AUDELA products and features.
Each product (Finance, BI, Credit, Project, IFRS9) has detailed tutorials with multilingual support.

The tutorial structure includes:
- Main product tutorials
- Feature-specific tutorials
- Navigation and menu tutorials
- Copy-to-clipboard quick links
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TutorialLink:
    """Represents a single tutorial link with metadata."""
    label: str  # msgid for the label
    url: str    # URL or anchor to tutorial
    icon: str   # Optional icon class


TUTORIAL_CONFIG: dict[str, dict[str, Any]] = {
    # ==================== FINANCE ====================
    "finance": {
        "main_tutorial": {
            "label": "Tutoriel Finance",
            "description": "Tutoriel complet Finance",
        },
        "menu_items": {
            "dashboard": {
                "label": "Tutoriel Tableau de bord Finance",
                "url": "/help/finance/dashboard",
            },
            "cash_management": {
                "label": "Tutoriel Gestion de trésorerie",
                "url": "/help/finance/cash-management",
            },
            "bank_reconciliation": {
                "label": "Tutoriel Rapprochement bancaire",
                "url": "/help/finance/bank-reconciliation",
            },
            "forecasting": {
                "label": "Tutoriel Prévisions financières",
                "url": "/help/finance/forecasting",
            },
            "compliance": {
                "label": "Tutoriel Conformité et audit",
                "url": "/help/finance/compliance",
            },
            "reporting": {
                "label": "Tutoriel Rapports financiers",
                "url": "/help/finance/reporting",
            },
            "multi_entity": {
                "label": "Tutoriel Gestion multi-entités",
                "url": "/help/finance/multi-entity",
            },
            "liquidity": {
                "label": "Tutoriel Analyse de liquidité",
                "url": "/help/finance/liquidity",
            },
        }
    },

    # ==================== BI ====================
    "bi": {
        "main_tutorial": {
            "label": "Tutoriel BI",
            "description": "Tutoriel complet Business Intelligence",
        },
        "menu_items": {
            "dashboards": {
                "label": "Tutoriel Tableaux de bord",
                "url": "/help/bi/dashboards",
            },
            "data_sources": {
                "label": "Tutoriel Sources de données",
                "url": "/help/bi/data-sources",
            },
            "queries": {
                "label": "Tutoriel Requêtes SQL",
                "url": "/help/bi/queries",
            },
            "visualizations": {
                "label": "Tutoriel Visualisations",
                "url": "/help/bi/visualizations",
            },
            "reports": {
                "label": "Tutoriel Rapports",
                "url": "/help/bi/reports",
            },
            "sharing": {
                "label": "Tutoriel Partage et permissions",
                "url": "/help/bi/sharing",
            },
            "ai_assistant": {
                "label": "Tutoriel Assistant IA",
                "url": "/help/bi/ai-assistant",
            },
            "exports": {
                "label": "Tutoriel Exports et téléchargements",
                "url": "/help/bi/exports",
            },
        }
    },

    # ==================== CREDIT ====================
    "credit": {
        "main_tutorial": {
            "label": "Tutoriel Audela Credit",
            "description": "Tutoriel complet Origination de crédit",
        },
        "menu_items": {
            "borrowers": {
                "label": "Tutoriel Gestion des emprunteurs",
                "url": "/help/credit/borrowers",
            },
            "deals": {
                "label": "Tutoriel Gestion des dossiers",
                "url": "/help/credit/deals",
            },
            "facilities": {
                "label": "Tutoriel Gestion des facilités",
                "url": "/help/credit/facilities",
            },
            "collateral": {
                "label": "Tutoriel Gestion des collatéraux",
                "url": "/help/credit/collateral",
            },
            "guarantors": {
                "label": "Tutoriel Gestion des garants",
                "url": "/help/credit/guarantors",
            },
            "spreading": {
                "label": "Tutoriel Étalement des états financiers",
                "url": "/help/credit/spreading",
            },
            "ratios": {
                "label": "Tutoriel Calcul des ratios",
                "url": "/help/credit/ratios",
            },
            "credit_memo": {
                "label": "Tutoriel Mémo de crédit",
                "url": "/help/credit/credit-memo",
            },
            "workflow": {
                "label": "Tutoriel Workflow d'approbation",
                "url": "/help/credit/workflow",
            },
            "committee": {
                "label": "Tutoriel Comité de crédit",
                "url": "/help/credit/committee",
            },
            "portfolio": {
                "label": "Tutoriel Suivi du portefeuille",
                "url": "/help/credit/portfolio",
            },
        }
    },

    # ==================== PROJECT MANAGEMENT ====================
    "project": {
        "main_tutorial": {
            "label": "Tutoriel Gestion de projets",
            "description": "Tutoriel complet Gestion de projets",
        },
        "menu_items": {
            "portfolio": {
                "label": "Tutoriel Vue portefeuille",
                "url": "/help/project/portfolio",
            },
            "planning": {
                "label": "Tutoriel Planification",
                "url": "/help/project/planning",
            },
            "risks": {
                "label": "Tutoriel Gestion des risques",
                "url": "/help/project/risks",
            },
            "dependencies": {
                "label": "Tutoriel Dépendances",
                "url": "/help/project/dependencies",
            },
            "kanban": {
                "label": "Tutoriel Vue Kanban",
                "url": "/help/project/kanban",
            },
            "gantt": {
                "label": "Tutoriel Diagramme de Gantt",
                "url": "/help/project/gantt",
            },
            "tracking": {
                "label": "Tutoriel Suivi d'avancement",
                "url": "/help/project/tracking",
            },
            "decisions": {
                "label": "Tutoriel Gestion des décisions",
                "url": "/help/project/decisions",
            },
            "changes": {
                "label": "Tutoriel Gestion des changements",
                "url": "/help/project/changes",
            },
            "incidents": {
                "label": "Tutoriel Gestion des incidents",
                "url": "/help/project/incidents",
            },
            "reporting": {
                "label": "Tutoriel Reporting du projet",
                "url": "/help/project/reporting",
            },
            "governance": {
                "label": "Tutoriel Gouvernance",
                "url": "/help/project/governance",
            },
        }
    },

    # ==================== IFRS9 ====================
    "ifrs9": {
        "main_tutorial": {
            "label": "Tutoriel IFRS9",
            "description": "Tutoriel complet Provisionnement IFRS9",
        },
        "menu_items": {
            "staging": {
                "label": "Tutoriel Classification de risque (Staging)",
                "url": "/help/ifrs9/staging",
            },
            "parameters": {
                "label": "Tutoriel Paramètres ECL",
                "url": "/help/ifrs9/parameters",
            },
            "calculation": {
                "label": "Tutoriel Calcul ECL",
                "url": "/help/ifrs9/calculation",
            },
            "reporting": {
                "label": "Tutoriel Rapports IFRS9",
                "url": "/help/ifrs9/reporting",
            },
            "audit": {
                "label": "Tutoriel Piste d'audit",
                "url": "/help/ifrs9/audit",
            },
        }
    },

    # ==================== ETL ====================
    "etl": {
        "main_tutorial": {
            "label": "Tutoriel ETL",
            "description": "Tutoriel complet Extract-Transform-Load",
        },
        "menu_items": {
            "connections": {
                "label": "Tutoriel Gestion des connexions",
                "url": "/help/etl/connections",
            },
            "workflows": {
                "label": "Tutoriel Workflows ETL",
                "url": "/help/etl/workflows",
            },
            "transformations": {
                "label": "Tutoriel Transformations de données",
                "url": "/help/etl/transformations",
            },
            "scheduling": {
                "label": "Tutoriel Planification des jobs",
                "url": "/help/etl/scheduling",
            },
            "monitoring": {
                "label": "Tutoriel Suivi et logs",
                "url": "/help/etl/monitoring",
            },
        }
    },

    # ==================== COMMON/PORTAL ====================
    "portal": {
        "main_tutorial": {
            "label": "Tutoriel Portail",
            "description": "Tutoriel d'utilisation du portail",
        },
        "menu_items": {
            "navigation": {
                "label": "Tutoriel Navigation",
                "url": "/help/portal/navigation",
            },
            "user_settings": {
                "label": "Tutoriel Paramètres utilisateur",
                "url": "/help/portal/user-settings",
            },
            "permissions": {
                "label": "Tutoriel Gestion des permissions",
                "url": "/help/portal/permissions",
            },
            "workspaces": {
                "label": "Tutoriel Espaces de travail",
                "url": "/help/portal/workspaces",
            },
            "search": {
                "label": "Tutoriel Recherche",
                "url": "/help/portal/search",
            },
            "profile": {
                "label": "Tutoriel Profil utilisateur",
                "url": "/help/portal/profile",
            },
        }
    },
}


def get_product_tutorials(product: str) -> dict[str, Any] | None:
    """Get all tutorials for a specific product."""
    return TUTORIAL_CONFIG.get(product)


def get_product_menu_tutorials(product: str) -> dict[str, dict[str, str]] | None:
    """Get menu item tutorials for a specific product."""
    product_config = TUTORIAL_CONFIG.get(product)
    if product_config:
        return product_config.get("menu_items")
    return None


def get_all_tutorial_labels() -> list[str]:
    """Extract all msgids that need translation from tutorial config."""
    labels = []
    for product, config in TUTORIAL_CONFIG.items():
        if "main_tutorial" in config:
            labels.append(config["main_tutorial"]["label"])
        if "menu_items" in config:
            for item_key, item_config in config["menu_items"].items():
                labels.append(item_config["label"])
    return list(set(labels))


if __name__ == "__main__":
    # Quick test to list all labels
    all_labels = get_all_tutorial_labels()
    print(f"Total unique tutorial labels to translate: {len(all_labels)}")
    for label in sorted(all_labels):
        print(f"  - {label}")
