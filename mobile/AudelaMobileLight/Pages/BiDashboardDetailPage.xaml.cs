using AudelaMobileLight.Models;

namespace AudelaMobileLight.Pages;

public partial class BiDashboardDetailPage : ContentPage
{
    public string DashboardName { get; }
    public string MetaLabel { get; }
    public double LoadRatio { get; }
    public double CardsCoverageRatio { get; }
    public double FreshnessRatio { get; }
    public string DetailLine1 { get; }
    public string DetailLine2 { get; }
    public string DetailLine3 { get; }

    public BiDashboardDetailPage(MobileBiDashboardSummary dashboard)
    {
        DashboardName = dashboard.Name;
        MetaLabel = dashboard.MetaLabel;

        var cards = Math.Max(0, dashboard.CardsCount);
        LoadRatio = Math.Clamp(cards / 10.0, 0.08, 1.0);
        CardsCoverageRatio = Math.Clamp(cards / 8.0, 0.05, 1.0);
        FreshnessRatio = ComputeFreshnessRatio(dashboard.UpdatedAt);

        DetailLine1 = $"Cartes: {cards}";
        DetailLine2 = $"Principal: {(dashboard.IsPrimary ? "Oui" : "Non")}";
        DetailLine3 = string.IsNullOrWhiteSpace(dashboard.UpdatedAt)
            ? "Derniere mise a jour: n/a"
            : $"Derniere mise a jour: {dashboard.UpdatedAt}";

        InitializeComponent();
        BindingContext = this;
    }

    private static double ComputeFreshnessRatio(string updatedAt)
    {
        if (!DateTime.TryParse(updatedAt, out var updated))
        {
            return 0.45;
        }

        var days = Math.Max(0.0, (DateTime.UtcNow - updated.ToUniversalTime()).TotalDays);
        var ratio = 1.0 - (days / 14.0);
        return Math.Clamp(ratio, 0.05, 1.0);
    }
}
