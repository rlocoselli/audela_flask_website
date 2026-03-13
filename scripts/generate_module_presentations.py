#!/usr/bin/env python3
"""Generate stylized AUDELA PDF presentations.

Outputs:
- one PDF per module
- one consolidated PDF with all modules
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "module_presentations"

BRAND_BG = colors.HexColor("#fff3e8")
BRAND_BORDER = colors.HexColor("#ffc9a3")
BRAND_PILL = colors.HexColor("#f97316")
BRAND_TITLE = colors.HexColor("#7c2d12")
BRAND_SUBTITLE = colors.HexColor("#9a3412")
SECTION_COLOR = colors.HexColor("#ea580c")
TABLE_HEADER = colors.HexColor("#f97316")

MODULES: dict[str, dict[str, object]] = {
    "portal": {
        "title": "AUDELA Portal BI",
        "tagline": "Pilotage BI centralise pour les equipes metier et data.",
        "use_cases": [
            "Connecter les sources, preparer les donnees et lancer des analyses operationnelles.",
            "Executer des requetes SQL, sauvegarder des questions et construire des dashboards metiers.",
            "Utiliser BI Lite, Chat IA, What-if scenarios, alerting et statistiques pour accelerer la decision.",
        ],
        "capabilities": [
            ("Gestion des sources de donnees et workspaces avec jointures fichiers + DB", "Centralisation de toutes les donnees en un point unique, fin des silos."),
            ("SQL Editor, Questions, Dashboards, Reports, Explore, Runs, Audit", "Autonomie des equipes data sans outil externe ni licence additionnelle."),
            ("BI Lite, executive HTML, visualisations IA et simulation What-if", "Acces decisionnel pour profils non techniques et direction."),
            ("Gouvernance multi-tenant avec suivi d'usage", "Controle fin de qui accede a quoi, conformite et audit facilites."),
        ],
        "advantages": [
            "Reduction de 60-80 % du temps de preparation de dashboards vs Excel.",
            "Decision 3x plus rapide grace aux What-if scenarios sur donnees reelles.",
            "Elimination des allers-retours IT pour les demandes BI courantes.",
        ],
        "differentiators": [
            "Un meme portail combine SQL expert + BI Lite pour profils non techniques.",
            "Simulation What-if scenario directement reliee aux donnees de production.",
            "Traçabilite native (runs, audit) pour une BI gouvernee.",
        ],
    },
    "finance": {
        "title": "AUDELA Finance",
        "tagline": "Gestion financiere, tresorerie et suivi de performance.",
        "use_cases": [
            "Structurer le plan de comptes et piloter les operations de tresorerie.",
            "Suivre facturation, depenses, contreparties et soldes en temps reel.",
            "Produire des rapports et KPI financiers pour le management.",
        ],
        "capabilities": [
            ("Comptes, ecritures, pieces et flux de tresorerie", "Suivi en temps reel de la position cash et des ecarts budgetaires."),
            ("Factures clients/fournisseurs et suivi de statuts", "Reduction des retards de paiement et optimisation du BFR."),
            ("Ratios, reporting et statistiques financieres", "KPI automatises pour cloture plus rapide et moins d'erreurs."),
            ("Base prete pour regles de conformite et extensions ERP", "Transition vers normes reglementaires sans reconstruction."),
        ],
        "advantages": [
            "Vision consolidee de la tresorerie en un clic, sans tableur.",
            "Anticipation des ecarts budgetaires grace au suivi continu.",
            "Cycle de cloture reduit de plusieurs jours grace a la structuration.",
        ],
        "differentiators": [
            "Lien natif avec la BI pour passer de la compta a l'analyse decisionnelle.",
            "Modele evolutif vers scenarios previsionnels et simulations What-if.",
            "Conception multi-tenant adaptee aux groupes multi-filiales.",
        ],
    },
    "credit": {
        "title": "AUDELA Credit",
        "tagline": "Evaluation du risque credit et suivi des portefeuilles.",
        "use_cases": [
            "Qualifier la solvabilite des dossiers et prioriser les actions.",
            "Surveiller la qualite du portefeuille et les signaux de deterioration.",
            "Industrialiser les analyses via workflows et API internes.",
        ],
        "capabilities": [
            ("Workflows d'analyse credit et readiness checks", "Instruction des dossiers 2x plus rapide avec controles integres."),
            ("Scoring, segmentation et tableaux de suivi risque", "Identification precoce des dossiers a risque avant deterioration."),
            ("Integration de donnees financieres et operationnelles", "Analyse enrichie combinant comptabilite, tresorerie et signaux metier."),
            ("Tracabilite des decisions et support des audits", "Evidence d'audit complete pour regulateurs et controles internes."),
        ],
        "advantages": [
            "Acceleration de l'instruction : delai divise par 2 sur les dossiers standards.",
            "Detection precoce des signaux faibles avant impact sur le portefeuille.",
            "Standardisation des pratiques d'analyse pour fiabilite et reproductibilite.",
        ],
        "differentiators": [
            "Workflows metier prets a l'emploi avec capacite d'adaptation locale.",
            "Combinaison scoring + signaux operationnels + scenarios de stress What-if.",
            "Traçabilite end-to-end pour audit interne et reglementaire.",
        ],
    },
    "ifrs9": {
        "title": "AUDELA IFRS9",
        "tagline": "Cadre IFRS 9 pour pertes attendues et gouvernance du risque.",
        "use_cases": [
            "Calculer et documenter les approches ECL (Expected Credit Loss).",
            "Structurer le suivi Stage 1/2/3 et les hypotheses de scenario.",
            "Produire des vues de synthese pour controle interne et direction.",
        ],
        "capabilities": [
            ("Suivi des expositions et segmentation IFRS 9", "Vision claire des encours par stade de risque en temps reel."),
            ("Parametrage hypotheses, sensibilites et stress scenarios", "Simulation d'impact avant decision pour comite de risque."),
            ("Consolidation de resultats pour reporting reglementaire", "Production de rapports conformes sans ressaisie manuelle."),
            ("Pistes d'audit et gouvernance des modeles", "Conformite prouvee lors des controles regulateurs."),
        ],
        "advantages": [
            "Production ECL robuste avec piste d'audit complete.",
            "Reduction du risque de non-conformite par standardisation.",
            "Explicabilite des hypotheses pour les comites de risque et la direction.",
        ],
        "differentiators": [
            "Approche IFRS9 orientee gouvernance et preuve d'audit native.",
            "Stress scenarios et sensibilites integres dans le flux de travail.",
            "Connexion naturelle aux modules Credit et BI pour pilotage global.",
        ],
    },
    "etl": {
        "title": "AUDELA ETL",
        "tagline": "Pipelines data pour alimenter les modules metier.",
        "use_cases": [
            "Construire des flux d'ingestion et de transformation repetables.",
            "Unifier des sources heterogenes en datasets exploitables.",
            "Orchestrer des jobs et controler les executions.",
        ],
        "capabilities": [
            ("ETL Builder visuel et composants de transformation", "Construction de pipelines sans code, accessible aux analystes."),
            ("Planification/relance des runs et historique d'execution", "Automatisation des traitements recurrents, economies de temps."),
            ("Qualite de donnees et normalisation des schemas", "Donnees fiables en entree, analyses fiables en sortie."),
            ("Integration native avec workspaces et dashboards", "Flux de bout en bout sans rupture entre ingestion et analyse."),
        ],
        "advantages": [
            "Elimination des manipulations manuelles repetitives sur fichiers.",
            "Fiabilite des donnees alimentant les dashboards et les modeles.",
            "Time-to-insight reduit : de la source brute au dashboard en minutes.",
        ],
        "differentiators": [
            "ETL builder visuel connecte directement au portail BI.",
            "Run history exploitable pour traçabilite et diagnostic.",
            "Approche modulaire pour industrialiser progressivement.",
        ],
    },
    "project": {
        "title": "AUDELA Project",
        "tagline": "Pilotage projet et execution collaborative.",
        "use_cases": [
            "Organiser roadmap, backlog et livrables.",
            "Suivre avancement, dependances et priorites en equipe.",
            "Partager une vision commune entre metier, data et IT.",
        ],
        "capabilities": [
            ("Hub projets avec vues kanban et suivi de taches", "Visibilite immediate sur l'avancement et les blocages."),
            ("Cartes actionnables, statuts et ownership", "Responsabilisation claire, moins de reunions de suivi."),
            ("Historique des modifications et tracabilite", "Memoire projet complete pour retrospectives et audit."),
            ("Lien naturel avec modules BI/Finance pour pilotage global", "Decisions projet eclairees par les indicateurs business reels."),
        ],
        "advantages": [
            "Alignement des equipes sur priorites et delivrables en un coup d'oeil.",
            "Reduction des reunions de suivi grace a la visibilite temps reel.",
            "Execution plus previsible avec alertes sur les dependances.",
        ],
        "differentiators": [
            "Pilotage projet connecte aux donnees business reelles.",
            "Traçabilite operationnelle utile aux comites de direction.",
            "Pont natif entre execution projet et indicateurs BI.",
        ],
    },
    "billing": {
        "title": "AUDELA Billing",
        "tagline": "Abonnements, plans et facturation SaaS.",
        "use_cases": [
            "Configurer offres et regles de souscription.",
            "Suivre l'etat des abonnements et la consommation.",
            "Appuyer les operations de revenu recurrent.",
        ],
        "capabilities": [
            ("Gestion des plans, cycles et etats d'abonnement", "Maitrise du MRR et suivi du churn en temps reel."),
            ("Integration de paiement et webhooks de statut", "Encaissements automatises, moins de relances manuelles."),
            ("Controle d'acces selon niveau d'offre", "Upsell naturel : acces module lie au plan souscrit."),
            ("Support des scenarios d'essai, upgrade et renouvellement", "Parcours client fluide, reduction de la friction commerciale."),
        ],
        "advantages": [
            "Maitrise du revenu recurrent avec metriques MRR/churn integrees.",
            "Moins de friction dans les evolutions d'abonnement client.",
            "Pilotage commercial lie aux acces produit reels.",
        ],
        "differentiators": [
            "Billing connecte aux modules metiers et aux droits applicatifs.",
            "Vision unifiee entre etat client, plan et acces reel.",
            "Architecture prete pour offres enterprise multi-niveaux.",
        ],
    },
    "tenant": {
        "title": "AUDELA Tenant",
        "tagline": "Administration multi-tenant et personnalisation.",
        "use_cases": [
            "Isoler les donnees et parametrages par organisation.",
            "Gerer identite visuelle et profil de tenant.",
            "Superviser l'acces et la securite organisationnelle.",
        ],
        "capabilities": [
            ("Provisioning tenant et onboarding", "Nouveau client operationnel en quelques minutes."),
            ("Branding tenant (nom, logo, preferences)", "Experience marque blanche sans developpement specifique."),
            ("Administration utilisateurs et securite d'acces", "Controle fin des roles et permissions par organisation."),
            ("Isolation stricte des espaces et donnees", "Zero risque de fuite de donnees entre organisations."),
        ],
        "advantages": [
            "Isolation forte garantissant la confidentialite par organisation.",
            "Onboarding client en minutes au lieu de jours.",
            "Personnalisation marque blanche sans complexite technique.",
        ],
        "differentiators": [
            "Modele multi-tenant pense pour scalabilite B2B.",
            "Branding et securite reunis dans un meme socle.",
            "Architecture prete pour groupes multi-entites.",
        ],
    },
    "admin": {
        "title": "AUDELA Admin",
        "tagline": "Supervision technique et gouvernance applicative.",
        "use_cases": [
            "Observer l'etat de la plateforme et les indicateurs clefs.",
            "Piloter la configuration globale et les operations sensibles.",
            "Garantir la conformite et la resilience du service.",
        ],
        "capabilities": [
            ("Administration globale des composants", "Vue unifiee de tous les modules depuis un seul panneau."),
            ("Suivi des evenements et operations critiques", "Detection rapide des anomalies avant impact utilisateur."),
            ("Outils de diagnostic et maintenance", "Resolution plus rapide, MTTR reduit."),
            ("Support de gouvernance securite et audit", "Evidence de conformite prete pour controles internes."),
        ],
        "advantages": [
            "Visibilite 360 sur la sante de la plateforme.",
            "Temps de resolution des incidents divise par la centralisation.",
            "Conformite prouvable avec pistes d'audit integrees.",
        ],
        "differentiators": [
            "Poste de controle transversal sur tous les modules.",
            "Approche governance-first avec evidences auditables.",
            "Concu pour supervision continue en contexte SaaS.",
        ],
    },
    "auth": {
        "title": "AUDELA Auth",
        "tagline": "Authentification, controle d'acces et securite utilisateur.",
        "use_cases": [
            "Gerer connexion, deconnexion et cycle de vie des comptes.",
            "Appliquer des politiques de mot de passe et verification.",
            "Renforcer la securite des parcours applicatifs.",
        ],
        "capabilities": [
            ("Login/logout et gestion de session", "Experience de connexion rapide et securisee."),
            ("Changement de mot de passe et verification email", "Self-service utilisateur, moins de tickets support."),
            ("Garde-fous CSRF et protections de formulaires", "Protection contre les attaques web courantes."),
            ("Base pour extensions MFA et politiques de securite", "Chemin d'evolution vers conformite securitaire avancee."),
        ],
        "advantages": [
            "Securisation des parcours utilisateurs sans friction.",
            "Reduction des tickets d'assistance lies aux mots de passe.",
            "Socle unique de securite pour tous les modules applicatifs.",
        ],
        "differentiators": [
            "Socle auth pense pour multi-tenant et roles metiers.",
            "Integration native avec les controles de securite applicatifs.",
            "Evolution simple vers MFA et politiques avancees.",
        ],
    },
    "public": {
        "title": "AUDELA Public",
        "tagline": "Site vitrine, pages legales et conversion commerciale.",
        "use_cases": [
            "Presenter les offres et cas d'usage AUDELA.",
            "Fournir les pages legales et informations de confiance.",
            "Convertir visiteurs vers espaces tenant et produits.",
        ],
        "capabilities": [
            ("Pages marketing, produits et contenus institutionnels", "Acquisition de prospects avec message produit clair."),
            ("Mentions legales, privacy, terms, cookies et retention", "Conformite RGPD et e-privacy sans effort additionnel."),
            ("Points d'entree vers authentification et onboarding", "Conversion visitor-to-user en parcours fluide."),
            ("Support multilingue pour audience internationale", "Expansion geographique sans refonte du site."),
        ],
        "advantages": [
            "Taux de conversion ameliore par un parcours site-vers-produit continu.",
            "Conformite legale integree, pas de chantier juridique separe.",
            "Message coherent entre vitrine et experience produit.",
        ],
        "differentiators": [
            "Couplage direct entre site vitrine et plateforme operationnelle.",
            "Contenus multilingues prets pour expansion internationale.",
            "Base marketing legal-tech-data sur une meme marque.",
        ],
    },
}


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleAudela",
            parent=base["Heading1"],
            fontSize=18,
            leading=22,
            textColor=BRAND_TITLE,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "SubAudela",
            parent=base["Normal"],
            fontSize=10.5,
            leading=14,
            textColor=BRAND_SUBTITLE,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "SectionAudela",
            parent=base["Heading2"],
            fontSize=13,
            leading=16,
            textColor=SECTION_COLOR,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "BodyAudela",
            parent=base["Normal"],
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#3f2a1d"),
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "SmallAudela",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#9a6a4f"),
        ),
        "logo": ParagraphStyle(
            "LogoAudela",
            parent=base["Normal"],
            fontSize=14,
            leading=17,
            textColor=colors.white,
            alignment=1,
        ),
    }


def build_module_story(module: dict[str, object], styles: dict[str, ParagraphStyle]) -> list[object]:
    story: list[object] = []

    logo_pill = Table([[Paragraph("<b>AUDELA</b>", styles["logo"])]], colWidths=[42 * mm])
    logo_pill.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_PILL),
                ("BOX", (0, 0), (-1, -1), 0.6, BRAND_PILL),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    top = Table(
        [[logo_pill, Paragraph(f"<b>{module.get('title', '')}</b><br/>{module.get('tagline', '')}", styles["subtitle"])]],
        colWidths=[48 * mm, 120 * mm],
    )
    top.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_BG),
                ("BOX", (0, 0), (-1, -1), 1, BRAND_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(top)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Ce que ce module permet", styles["section"]))
    for item in module.get("use_cases", []):
        story.append(Paragraph(f"- {item}", styles["body"]))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Fonctionnalites cles", styles["section"]))

    cap_rows = [["Capacite", "Valeur metier"]]
    for cap in module.get("capabilities", []):
        if isinstance(cap, tuple):
            cap_rows.append([cap[0], cap[1]])
        else:
            cap_rows.append([cap, ""])

    tbl = Table(cap_rows, colWidths=[104 * mm, 56 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fffaf5"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ffd8bf")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tbl)

    advantages = module.get("advantages", [])
    if isinstance(advantages, list) and advantages:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Avantages business", styles["section"]))
        for item in advantages:
            story.append(Paragraph(f"- {item}", styles["body"]))

    differentiators = module.get("differentiators", [])
    if isinstance(differentiators, list) and differentiators:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Differenciants AUDELA", styles["section"]))
        for item in differentiators:
            story.append(Paragraph(f"- {item}", styles["body"]))

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Recommandation: commencer par un pilote metier de 2 a 4 semaines, puis industrialiser le module avec vos regles internes.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"Document genere le {date.today().isoformat()} - AUDELA", styles["small"]))

    return story


def build_pdf(module_key: str, module: dict[str, object], styles: dict[str, ParagraphStyle]) -> None:
    out_file = OUT_DIR / f"{module_key}_presentation_audela.pdf"

    doc = SimpleDocTemplate(
        str(out_file),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"AUDELA - Presentation module {module_key}",
        author="AUDELA",
    )
    doc.build(build_module_story(module, styles))


def build_master_pdf(styles: dict[str, ParagraphStyle]) -> None:
    out_file = OUT_DIR / "audela_modules_presentation_complete.pdf"
    doc = SimpleDocTemplate(
        str(out_file),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="AUDELA - Presentation complete des modules",
        author="AUDELA",
    )

    module_items = list(MODULES.items())
    story: list[object] = []
    for idx, (_, module_data) in enumerate(module_items):
        story.extend(build_module_story(module_data, styles))
        if idx < len(module_items) - 1:
            story.append(PageBreak())

    doc.build(story)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    styles = build_styles()

    build_master_pdf(styles)
    print(f"Generated consolidated PDF in: {OUT_DIR}")


if __name__ == "__main__":
    main()
