namespace AudelaMobileLight.Models;

public sealed class MobileDashboardMetrics
{
    public int DashboardCount { get; set; }
    public int QueryRunCount { get; set; }
    public int FinanceEntriesCount { get; set; }
    public double FinanceNetAmount { get; set; }
    public int LearningModulesCount { get; set; }
    public int LearningProgressAvg { get; set; }
    public int KanbanBacklog { get; set; }
    public int KanbanTodo { get; set; }
    public int KanbanDoing { get; set; }
    public int KanbanDone { get; set; }
}
