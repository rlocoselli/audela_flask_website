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
    public string VizTypeNormalized { get; set; } = "table";
    public string SourceName { get; set; } = string.Empty;
    public string PrimaryValue { get; set; } = string.Empty;
    public string SecondaryValue { get; set; } = string.Empty;
    public List<MobileBiPoint> Points { get; set; } = [];
    public List<string> PreviewRows { get; set; } = [];

    public bool IsKpi => VizTypeNormalized == "kpi";
    public bool IsBar => VizTypeNormalized == "bar";
    public bool IsPie => VizTypeNormalized == "pie";
    public bool IsLine => VizTypeNormalized == "line";
    public bool IsTable => VizTypeNormalized == "table";

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
