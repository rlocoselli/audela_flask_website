using Microsoft.Maui.Graphics;

namespace AudelaMobileLight.Models;

public sealed class MobileFinanceAccount
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string AccountType { get; set; } = string.Empty;

    public string DisplayName
    {
        get
        {
            var type = string.IsNullOrWhiteSpace(AccountType) ? string.Empty : $" ({AccountType})";
            return $"{Name}{type}";
        }
    }
}

public sealed class MobileFinanceCategoryTotal
{
    public string Category { get; set; } = string.Empty;
    public double Amount { get; set; }
    public int TransactionsCount { get; set; }

    public string AmountLabel => $"{Amount:0.00}";
    public string MetaLabel => $"{TransactionsCount} operations";
    public Color AmountColor => Color.FromArgb("#1B6E3E");
}

public sealed class MobileFinanceCategoryReport
{
    public List<MobileFinanceCategoryTotal> Expenses { get; set; } = [];
    public List<MobileFinanceCategoryTotal> Revenues { get; set; } = [];
}
