using Microsoft.Maui.Graphics;

namespace AudelaMobileLight.Models;

public sealed class MobileFinanceEntry
{
    public int Id { get; set; }
    public string Date { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public double Amount { get; set; }
    public string Account { get; set; } = string.Empty;
    public string Category { get; set; } = string.Empty;

    public string AmountLabel => Amount >= 0 ? $"+{Amount:0.00}" : $"{Amount:0.00}";
    public Color AmountColor => Amount >= 0 ? Color.FromArgb("#1F8A4D") : Color.FromArgb("#9F2C2C");
}
