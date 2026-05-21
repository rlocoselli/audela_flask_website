using System.Collections.ObjectModel;
using System.Globalization;
using System.Text.RegularExpressions;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class BiDashboardDetailPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly int _dashboardId;
    public ObservableCollection<MobileBiDashboardCard> Cards { get; } = [];

    public string DashboardName { get; private set; }
    public string MetaLabel { get; private set; }
    public double LoadRatio { get; private set; }
    public double CardsCoverageRatio { get; private set; }
    public double FreshnessRatio { get; private set; }
    public string DetailLine1 { get; private set; }
    public string DetailLine2 { get; private set; }
    public string DetailLine3 { get; private set; }
    public bool IsLoading { get; private set; }

    public BiDashboardDetailPage(MobileBiDashboardSummary dashboard)
    {
        _dashboardId = dashboard.Id;

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

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await LoadAsync();
    }

    private async Task LoadAsync()
    {
        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var detail = await _service.GetBiDashboardDetailAsync(_dashboardId, CancellationToken.None);
            if (detail is null)
            {
                return;
            }

            DashboardName = detail.Name;
            MetaLabel = $"Cards: {detail.CardsCount}" + (detail.IsPrimary ? " - primary" : string.Empty);
            LoadRatio = Math.Clamp(detail.CardsCount / 10.0, 0.08, 1.0);
            CardsCoverageRatio = Math.Clamp(detail.CardsCount / 8.0, 0.05, 1.0);
            FreshnessRatio = ComputeFreshnessRatio(detail.UpdatedAt);
            DetailLine1 = $"Cartes: {detail.CardsCount}";
            DetailLine2 = $"Principal: {(detail.IsPrimary ? "Oui" : "Non")}";
            DetailLine3 = string.IsNullOrWhiteSpace(detail.UpdatedAt)
                ? "Derniere mise a jour: n/a"
                : $"Derniere mise a jour: {detail.UpdatedAt}";

            Cards.Clear();
            foreach (var card in detail.Cards)
            {
                EnsureRenderablePoints(card);
                Cards.Add(card);
            }

            OnPropertyChanged(nameof(DashboardName));
            OnPropertyChanged(nameof(MetaLabel));
            OnPropertyChanged(nameof(LoadRatio));
            OnPropertyChanged(nameof(CardsCoverageRatio));
            OnPropertyChanged(nameof(FreshnessRatio));
            OnPropertyChanged(nameof(DetailLine1));
            OnPropertyChanged(nameof(DetailLine2));
            OnPropertyChanged(nameof(DetailLine3));
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
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

    private static void EnsureRenderablePoints(MobileBiDashboardCard card)
    {
        if (card is null)
        {
            return;
        }

        // For chart cards, synthesize lightweight points from preview rows when API points are missing.
        if (!(card.IsBar || card.IsLine || card.IsPie) || card.Points.Count > 0)
        {
            return;
        }

        var parsed = new List<MobileBiPoint>();
        foreach (var row in card.PreviewRows)
        {
            var point = TryParsePointFromPreviewRow(row, parsed.Count + 1);
            if (point is not null)
            {
                parsed.Add(point);
            }
        }

        if (parsed.Count == 0)
        {
            if (double.TryParse(NormalizeNumericToken(card.PrimaryValue), NumberStyles.Float, CultureInfo.InvariantCulture, out var primaryNumber))
            {
                parsed.Add(new MobileBiPoint { X = "value", Y = primaryNumber, Ratio = 1.0 });
            }
            else
            {
                return;
            }
        }

        var max = parsed.Max(p => Math.Abs(p.Y));
        if (max <= 0)
        {
            max = 1.0;
        }

        foreach (var p in parsed)
        {
            p.Ratio = Math.Clamp(Math.Abs(p.Y) / max, 0.08, 1.0);
            card.Points.Add(p);
        }
    }

    private static MobileBiPoint? TryParsePointFromPreviewRow(string? row, int index)
    {
        if (string.IsNullOrWhiteSpace(row))
        {
            return null;
        }

        var parts = row.Split('|', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        string label = $"row {index}";

        if (parts.Length > 0)
        {
            var firstPair = parts[0].Split(':', 2, StringSplitOptions.TrimEntries);
            if (firstPair.Length == 2 && !string.IsNullOrWhiteSpace(firstPair[1]))
            {
                label = firstPair[1];
            }
        }

        foreach (var part in parts)
        {
            var kv = part.Split(':', 2, StringSplitOptions.TrimEntries);
            if (kv.Length != 2)
            {
                continue;
            }

            var candidate = NormalizeNumericToken(kv[1]);
            if (!double.TryParse(candidate, NumberStyles.Float, CultureInfo.InvariantCulture, out var value))
            {
                continue;
            }

            return new MobileBiPoint
            {
                X = label,
                Y = value,
                Ratio = 0.0,
            };
        }

        // Last-chance extraction if values are embedded in free text.
        var match = Regex.Match(row, @"-?\d+(?:[\.,]\d+)?");
        if (match.Success)
        {
            var candidate = NormalizeNumericToken(match.Value);
            if (double.TryParse(candidate, NumberStyles.Float, CultureInfo.InvariantCulture, out var value))
            {
                return new MobileBiPoint
                {
                    X = label,
                    Y = value,
                    Ratio = 0.0,
                };
            }
        }

        return null;
    }

    private static string NormalizeNumericToken(string? raw)
    {
        var value = (raw ?? string.Empty).Trim();
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        value = value.Replace(" ", string.Empty);
        value = value.Replace(",", ".");
        return value;
    }
}
