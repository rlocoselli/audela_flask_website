namespace AudelaMobileLight.Models;

public sealed class MobileLearningEnrollment
{
    public string ModuleCode { get; set; } = string.Empty;
    public string ModuleTitle { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public int Progress { get; set; }
    public int Score { get; set; }

    public double ProgressRatio => Math.Clamp(Progress / 100.0, 0.0, 1.0);
    public string ProgressLabel => $"{Progress}% complete";
}
