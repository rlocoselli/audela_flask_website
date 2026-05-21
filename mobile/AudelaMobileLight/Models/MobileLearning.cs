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

public sealed class MobileLearningLesson
{
    public int Id { get; set; }
    public int ModuleId { get; set; }
    public string ModuleCode { get; set; } = string.Empty;
    public string ModuleTitle { get; set; } = string.Empty;
    public string LessonTitle { get; set; } = string.Empty;
    public string Summary { get; set; } = string.Empty;
}

public sealed class MobileLearningQuizSummary
{
    public int Id { get; set; }
    public int ModuleId { get; set; }
    public string ModuleCode { get; set; } = string.Empty;
    public string ModuleTitle { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public int QuestionCount { get; set; }
    public int PassingScorePct { get; set; }
    public string QuizLabel => $"{QuestionCount} questions - seuil {PassingScorePct}%";
}
