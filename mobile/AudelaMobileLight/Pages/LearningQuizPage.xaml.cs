using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class LearningQuizPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly int _quizId;

    public ObservableCollection<MobileLearningQuizQuestion> Questions { get; } = [];
    public ObservableCollection<QuizCorrectionItem> CorrectionItems { get; } = [];
    public bool IsLoading { get; private set; }
    public bool IsResultVisible { get; private set; }
    public string QuizTitle { get; private set; }
    public string QuizDescription { get; private set; } = string.Empty;
    public string PassingLabel { get; private set; } = string.Empty;
    public string AnsweredCountLabel { get; private set; } = "0 / 0 answered";
    public double AnsweredProgress { get; private set; }
    public string ResultSummary { get; private set; } = string.Empty;

    public LearningQuizPage(int quizId, string quizTitle)
    {
        _quizId = quizId;
        QuizTitle = string.IsNullOrWhiteSpace(quizTitle) ? "Quiz" : quizTitle;
        InitializeComponent();
        BindingContext = this;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await LoadAsync();
    }

    private async Task LoadAsync()
    {
        if (_quizId <= 0)
        {
            await ModernAlertService.ShowAsync(this, "Learning", "Quiz invalide.", AlertTone.Error);
            return;
        }

        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var detail = await _service.GetLearningQuizDetailAsync(_quizId, CancellationToken.None);
            if (detail is null)
            {
                await ModernAlertService.ShowAsync(this, "Learning", "Impossible de charger le quiz.", AlertTone.Error);
                return;
            }

            QuizTitle = string.IsNullOrWhiteSpace(detail.Title) ? QuizTitle : detail.Title;
            QuizDescription = detail.Description ?? string.Empty;
            PassingLabel = $"Score minimum: {detail.PassingScorePct}%";
            OnPropertyChanged(nameof(QuizTitle));
            OnPropertyChanged(nameof(QuizDescription));
            OnPropertyChanged(nameof(PassingLabel));

            Questions.Clear();
            foreach (var question in detail.Questions)
            {
                Questions.Add(question);
            }

            IsResultVisible = false;
            ResultSummary = string.Empty;
            CorrectionItems.Clear();
            OnPropertyChanged(nameof(IsResultVisible));
            OnPropertyChanged(nameof(ResultSummary));
            RecalculateProgress();
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnSubmitQuizClicked(object? sender, EventArgs e)
    {
        var answers = new Dictionary<string, object>();
        foreach (var question in Questions)
        {
            if (question.HasOptions)
            {
                if (question.SelectedOption is not null)
                {
                    answers[question.Id.ToString()] = question.SelectedOption.Id;
                }
            }
            else if (!string.IsNullOrWhiteSpace(question.AnswerText))
            {
                answers[question.Id.ToString()] = question.AnswerText.Trim();
            }
        }

        var (ok, message, result) = await _service.SubmitLearningQuizAsync(_quizId, answers, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Learning", message, AlertTone.Error);
            return;
        }

        if (result is null)
        {
            await ModernAlertService.ShowAsync(this, "Learning", message, AlertTone.Info);
            return;
        }

        ResultSummary = $"{message} - Score {result.ScorePct}% (seuil {result.PassingScorePct}%)";
        OnPropertyChanged(nameof(ResultSummary));

        CorrectionItems.Clear();
        var ordered = Questions.ToDictionary(q => q.Id, q => q);
        var index = 1;
        foreach (var item in result.Questions)
        {
            ordered.TryGetValue(item.QuestionId, out var sourceQuestion);
            var title = sourceQuestion is null ? $"Question {index}" : sourceQuestion.Text;
            CorrectionItems.Add(new QuizCorrectionItem
            {
                QuestionLabel = $"Q{index}: {title}",
                StatusLabel = item.Correct ? "Correct" : "A revoir",
                StatusColor = item.Correct ? Color.FromArgb("#1B6E3E") : Color.FromArgb("#A63A3A"),
                ScoreLabel = $"{item.Earned} / {item.Max} pts",
                Explanation = item.Explanation ?? string.Empty,
            });
            index += 1;
        }

        IsResultVisible = true;
        OnPropertyChanged(nameof(IsResultVisible));
        await ModernAlertService.ShowAsync(this, "Learning", ResultSummary, result.Passed ? AlertTone.Success : AlertTone.Info);
    }

    private void OnQuestionAnswerChanged(object? sender, EventArgs e)
    {
        RecalculateProgress();
    }

    private void OnQuestionTextChanged(object? sender, TextChangedEventArgs e)
    {
        RecalculateProgress();
    }

    private void RecalculateProgress()
    {
        var total = Questions.Count;
        var answered = 0;
        foreach (var question in Questions)
        {
            if (question.HasOptions)
            {
                if (question.SelectedOption is not null)
                {
                    answered += 1;
                }
                continue;
            }

            if (!string.IsNullOrWhiteSpace(question.AnswerText))
            {
                answered += 1;
            }
        }

        AnsweredCountLabel = $"{answered} / {total} answered";
        AnsweredProgress = total <= 0 ? 0.0 : Math.Clamp(answered / (double)total, 0.0, 1.0);
        OnPropertyChanged(nameof(AnsweredCountLabel));
        OnPropertyChanged(nameof(AnsweredProgress));
    }
}

public sealed class QuizCorrectionItem
{
    public string QuestionLabel { get; set; } = string.Empty;
    public string StatusLabel { get; set; } = string.Empty;
    public Color StatusColor { get; set; } = Colors.Black;
    public string ScoreLabel { get; set; } = string.Empty;
    public string Explanation { get; set; } = string.Empty;
    public bool HasExplanation => !string.IsNullOrWhiteSpace(Explanation);
}
