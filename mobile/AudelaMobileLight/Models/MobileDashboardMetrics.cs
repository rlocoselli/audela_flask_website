namespace AudelaMobileLight.Models;

public sealed class MobileDashboardMetrics
{
    public int DashboardCount { get; set; }
    public int QueryRunCount { get; set; }
    public int FinanceEntriesCount { get; set; }
    public double FinanceNetAmount { get; set; }
    public int LearningModulesCount { get; set; }
    public int LearningProgressAvg { get; set; }
}
