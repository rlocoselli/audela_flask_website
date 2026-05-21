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
