using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class LearningModuleDetailPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly int _moduleId;

    public ObservableCollection<MobileLearningLessonDetail> Lessons { get; } = [];
    public ObservableCollection<MobileLearningQuizSummary> Quizzes { get; } = [];

    public bool IsLoading { get; private set; }
    public string HeaderTitle { get; private set; }
    public string HeaderDescription { get; private set; } = string.Empty;

    public LearningModuleDetailPage(int moduleId, string moduleTitle)
    {
        _moduleId = moduleId;
        HeaderTitle = string.IsNullOrWhiteSpace(moduleTitle) ? "Module" : moduleTitle;
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
        if (_moduleId <= 0)
        {
            await ModernAlertService.ShowAsync(this, "Learning", "Module invalide.", AlertTone.Error);
            return;
        }

        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var detail = await _service.GetLearningModuleDetailAsync(_moduleId, CancellationToken.None);
            if (detail is null)
            {
                await ModernAlertService.ShowAsync(this, "Learning", "Impossible de charger le module.", AlertTone.Error);
                return;
            }

            HeaderTitle = string.IsNullOrWhiteSpace(detail.Title) ? HeaderTitle : detail.Title;
            HeaderDescription = detail.Description ?? string.Empty;
            OnPropertyChanged(nameof(HeaderTitle));
            OnPropertyChanged(nameof(HeaderDescription));

            Lessons.Clear();
            foreach (var lesson in detail.Lessons)
            {
                Lessons.Add(lesson);
            }

            Quizzes.Clear();
            foreach (var quiz in detail.Quizzes)
            {
                Quizzes.Add(quiz);
            }
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnStartQuizClicked(object? sender, EventArgs e)
    {
        if (sender is not Button button || button.CommandParameter is not MobileLearningQuizSummary quiz)
        {
            return;
        }

        await Navigation.PushAsync(new LearningQuizPage(quiz.Id, quiz.Title));
    }
}
