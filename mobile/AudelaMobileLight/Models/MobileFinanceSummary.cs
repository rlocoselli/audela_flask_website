namespace AudelaMobileLight.Models;

public sealed class MobileFinanceSummary
{
    public double DailyIn { get; set; }
    public double DailyOut { get; set; }
    public double DailyNet { get; set; }

    public double MonthlyIn { get; set; }
    public double MonthlyOut { get; set; }
    public double MonthlyNet { get; set; }
}
