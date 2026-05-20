using System.Net.Http.Json;
using AudelaMobileLight.Models;

namespace AudelaMobileLight.Services;

public sealed class ProductCatalogService
{
    private readonly HttpClient _httpClient = new()
    {
        Timeout = TimeSpan.FromSeconds(6),
    };

    private readonly IReadOnlyList<string> _baseUrls = BackendEndpoints.Candidates();

    public async Task<IReadOnlyList<AudelaProduct>> GetProductsAsync(CancellationToken cancellationToken)
    {
        foreach (var baseUrl in _baseUrls)
        {
            try
            {
                var url = $"{baseUrl}/api/mobile/products";
                var payload = await _httpClient.GetFromJsonAsync<MobileCatalogResponse>(url, cancellationToken);
                var items = payload?.Products ?? [];
                if (items.Count > 0)
                {
                    return items;
                }
            }
            catch
            {
                // Try next endpoint candidate before falling back to local seed data.
            }
        }

        return SeedProducts();
    }

    private static IReadOnlyList<AudelaProduct> SeedProducts()
    {
        return
        [
            new AudelaProduct
            {
                Id = "finance",
                Title = "AUDELA Finance",
                Subtitle = "Tresorerie et pilotage financier",
                Summary = "Vision cash multi-comptes, rapprochement et alertes critiques dans une interface mobile simple.",
                Audience = "Directions financieres et PME",
                Tag = "finance",
                FeatureHighlights = ["Cash management", "Previsions glissantes", "Conformite et audit"],
                OutcomeHighlights = ["Decisions plus rapides", "Reduction des taches manuelles"],
            },
            new AudelaProduct
            {
                Id = "bi",
                Title = "AUDELA BI",
                Subtitle = "Dashboards et analyses data",
                Summary = "Vue executive mobile des KPIs pour suivre la performance ou verifier les anomalies.",
                Audience = "Equipes data et metiers",
                Tag = "bi",
                FeatureHighlights = ["KPI consolides", "Sources SQL/API", "Analyse assistee"],
                OutcomeHighlights = ["Decisions basees sur les donnees", "Autonomie des equipes"],
            },
            new AudelaProduct
            {
                Id = "ml",
                Title = "AUDELA ML Studio",
                Subtitle = "Modeles predictifs relies a BI",
                Summary = "Acces mobile aux cas d'usage ML et au suivi du cycle de vie des modeles.",
                Audience = "Data scientists et analysts",
                Tag = "ml",
                FeatureHighlights = ["Entrainement supervise", "Versioning", "Scoring continu"],
                OutcomeHighlights = ["Mise en production acceleree", "Trajectoire MLOps claire"],
            },
            new AudelaProduct
            {
                Id = "credit",
                Title = "Audela Credit",
                Subtitle = "Origination de credit bancaire",
                Summary = "Vue mobile des dossiers, workflows et points de risque pour decisions plus fluides.",
                Audience = "Analystes credit et risk managers",
                Tag = "credit",
                FeatureHighlights = ["Borrowers et deals", "Credit memo", "Workflow approbation"],
                OutcomeHighlights = ["Meilleure traceabilite", "Decisions mieux documentees"],
            },
            new AudelaProduct
            {
                Id = "ifrs9",
                Title = "AUDELA IFRS9",
                Subtitle = "Socle ECL et staging",
                Summary = "Acces rapide aux informations IFRS9 et au perimetre de provisionnement en cours.",
                Audience = "Equipes risque et finance",
                Tag = "ifrs9",
                FeatureHighlights = ["Activation par abonnement", "Espace staging", "Preparation ECL"],
                OutcomeHighlights = ["Deploiement progressif", "Meilleure gouvernance risque"],
            },
            new AudelaProduct
            {
                Id = "project",
                Title = "AUDELA Projet",
                Subtitle = "Execution projet et PMO",
                Summary = "Suivi mobile des priorites, jalons et risques pour les equipes de delivery.",
                Audience = "PMO et chefs de projet",
                Tag = "project",
                FeatureHighlights = ["Portefeuille", "Gantt et Kanban", "Reporting gouvernance"],
                OutcomeHighlights = ["Meilleure visibilite", "Reduction des retards"],
            },
            new AudelaProduct
            {
                Id = "e_learning",
                Title = "AUDELA Academy",
                Subtitle = "Learning SQL et Data",
                Summary = "Parcours e-learning, progression et certifications consultables en mode mobile.",
                Audience = "Analystes, etudiants et reconversion",
                Tag = "academy",
                FeatureHighlights = ["Exercices interactifs", "Progression", "Certificats"],
                OutcomeHighlights = ["Competences SQL renforcees", "Motivation par gamification"],
            },
        ];
    }

    private sealed class MobileCatalogResponse
    {
        public List<AudelaProduct> Products { get; set; } = [];
    }
}
