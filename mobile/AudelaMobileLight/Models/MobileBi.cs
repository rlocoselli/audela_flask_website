namespace AudelaMobileLight.Models;

public sealed class MobileBiDataSource
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Type { get; set; } = string.Empty;
    public string Token { get; set; } = string.Empty;

    public string DisplayName => $"{Name} ({Type})";
}

public sealed class MobileBiDashboardSummary
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public int CardsCount { get; set; }
    public bool IsPrimary { get; set; }
    public string UpdatedAt { get; set; } = string.Empty;

    public string MetaLabel => $"Cards: {CardsCount}" + (IsPrimary ? " - primary" : string.Empty);
}

public sealed class MobileAiChatMessage
{
    public string Text { get; set; } = string.Empty;
    public bool IsUser { get; set; }
}

public sealed class MobileBiPoint
{
    public string X { get; set; } = string.Empty;
    public double Y { get; set; }
    public double Ratio { get; set; }
}

public sealed class MobileBiDashboardCard
{
    public int Id { get; set; }
    public string Title { get; set; } = string.Empty;
    public string VizType { get; set; } = string.Empty;
    private string _vizTypeNormalized = "table";
    public string VizTypeNormalized
    {
        get => _vizTypeNormalized;
        set => _vizTypeNormalized = string.IsNullOrWhiteSpace(value) ? "table" : value.Trim().ToLowerInvariant();
    }
    public string SourceName { get; set; } = string.Empty;
    public string PrimaryValue { get; set; } = string.Empty;
    public string SecondaryValue { get; set; } = string.Empty;
    public List<MobileBiPoint> Points { get; set; } = [];
    public List<string> PreviewRows { get; set; } = [];

    public bool IsKpi => string.Equals(VizTypeNormalized, "kpi", StringComparison.OrdinalIgnoreCase);
    public bool IsBar => string.Equals(VizTypeNormalized, "bar", StringComparison.OrdinalIgnoreCase) && !IsKpi;
    public bool IsPie => string.Equals(VizTypeNormalized, "pie", StringComparison.OrdinalIgnoreCase) && !IsKpi;
    public bool IsLine => string.Equals(VizTypeNormalized, "line", StringComparison.OrdinalIgnoreCase) && !IsKpi;
    public bool IsTable => string.Equals(VizTypeNormalized, "table", StringComparison.OrdinalIgnoreCase);

    public string VizVariant
    {
        get
        {
            var raw = (VizType ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(raw))
            {
                return VizTypeNormalized;
            }

            if (raw.Contains("donut") || raw.Contains("ring")) return "donut";
            if (raw.Contains("scatter") || raw.Contains("bubble")) return "scatter";
            if (raw.Contains("area")) return "area";
            if (raw.Contains("hist")) return "histogram";
            if (raw.Contains("spark")) return "sparkline";
            if (raw.Contains("pivot")) return "pivot";
            if (raw.Contains("gauge")) return "gauge";
            if (raw.Contains("kpi") || raw.Contains("metric") || raw.Contains("scorecard")) return "kpi";
            if (raw.Contains("line") || raw.Contains("trend") || raw.Contains("time") || raw.Contains("series")) return "line";
            if (raw.Contains("bar")) return "bar";
            if (raw.Contains("pie")) return "pie";
            if (raw.Contains("table")) return "table";
            return VizTypeNormalized;
        }
    }

    public string VizStyleKey
    {
        get
        {
            var variant = VizVariant;
            if (string.Equals(variant, "area", StringComparison.OrdinalIgnoreCase)
                || string.Equals(variant, "scatter", StringComparison.OrdinalIgnoreCase)
                || string.Equals(variant, "donut", StringComparison.OrdinalIgnoreCase))
            {
                return variant;
            }

            return VizTypeNormalized;
        }
    }

    public string DisplayVizLabel
    {
        get
        {
            var variant = VizVariant;
            if (string.Equals(variant, VizTypeNormalized, StringComparison.OrdinalIgnoreCase))
            {
                return VizTypeNormalized;
            }

            return $"{VizTypeNormalized} ({variant})";
        }
    }

    public string TrendLabel => Points.Count > 0 ? string.Join("  ", Points.Select(p => $"{p.X}:{p.Y:0.#}")) : "No points";
}

public sealed class MobileBiDashboardDetail
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public bool IsPrimary { get; set; }
    public string UpdatedAt { get; set; } = string.Empty;
    public int CardsCount { get; set; }
    public List<MobileBiDashboardCard> Cards { get; set; } = [];
}

public sealed class MobileBiQueryResult
{
    public List<string> Columns { get; set; } = [];
    public List<List<string>> Rows { get; set; } = [];
    public int ElapsedMs { get; set; }
}
