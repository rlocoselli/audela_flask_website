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

public sealed class MobileLearningModuleDetail
{
    public int Id { get; set; }
    public string Code { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public List<MobileLearningLessonDetail> Lessons { get; set; } = [];
    public List<MobileLearningQuizSummary> Quizzes { get; set; } = [];
}

public sealed class MobileLearningLessonDetail
{
    public int Id { get; set; }
    public string Code { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Summary { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
}

public sealed class MobileLearningQuizDetail
{
    public int Id { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public int PassingScorePct { get; set; }
    public bool ShowCorrectAnswers { get; set; }
    public List<MobileLearningQuizQuestion> Questions { get; set; } = [];
}

public sealed class MobileLearningQuizQuestion
{
    public int Id { get; set; }
    public string QuestionType { get; set; } = "multiple_choice";
    public string Text { get; set; } = string.Empty;
    public string Explanation { get; set; } = string.Empty;
    public int Points { get; set; }
    public List<MobileLearningQuizOption> Options { get; set; } = [];

    public MobileLearningQuizOption? SelectedOption { get; set; }
    public string AnswerText { get; set; } = string.Empty;
    public bool HasOptions => Options.Count > 0;
}

public sealed class MobileLearningQuizOption
{
    public int Id { get; set; }
    public string Text { get; set; } = string.Empty;
}

public sealed class MobileLearningQuizResult
{
    public int ScorePct { get; set; }
    public bool Passed { get; set; }
    public int PassingScorePct { get; set; }
    public int PointsEarned { get; set; }
    public int PointsTotal { get; set; }
    public List<MobileLearningQuizQuestionResult> Questions { get; set; } = [];
}

public sealed class MobileLearningQuizQuestionResult
{
    public int QuestionId { get; set; }
    public bool Correct { get; set; }
    public int Earned { get; set; }
    public int Max { get; set; }
    public string Explanation { get; set; } = string.Empty;
}
