using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class LearningPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public ObservableCollection<MobileLearningEnrollment> Enrollments { get; } = [];
    public ObservableCollection<MobileLearningLesson> Lessons { get; } = [];
    public ObservableCollection<MobileLearningQuizSummary> Quizzes { get; } = [];
    public ObservableCollection<MobileLearningLesson> SubscriptionModules { get; } = [];
    public MobileLearningLesson? SelectedSubscriptionModule { get; set; }
    public bool IsLoading { get; private set; }

    public LearningPage()
    {
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
        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var rows = await _service.GetLearningAsync(CancellationToken.None);
            var lessons = await _service.GetLearningContentAsync(CancellationToken.None);
            var quizzes = await _service.GetLearningQuizzesAsync(CancellationToken.None);
            Enrollments.Clear();
            foreach (var row in rows)
            {
                Enrollments.Add(row);
            }

            Lessons.Clear();
            foreach (var row in lessons)
            {
                Lessons.Add(row);
            }

            SubscriptionModules.Clear();
            foreach (var module in lessons
                .GroupBy(l => $"{l.ModuleId}:{l.ModuleCode}:{l.ModuleTitle}")
                .Select(g => g.First())
                .OrderBy(l => l.ModuleTitle))
            {
                SubscriptionModules.Add(module);
            }

            if (SubscriptionModules.Count == 0)
            {
                var fallback = rows
                    .Where(r => !string.IsNullOrWhiteSpace(r.ModuleCode) || !string.IsNullOrWhiteSpace(r.ModuleTitle))
                    .GroupBy(r => $"{r.ModuleCode}:{r.ModuleTitle}")
                    .Select(g => g.First())
                    .OrderBy(r => r.ModuleTitle)
                    .Select((r, idx) => new MobileLearningLesson
                    {
                        Id = idx + 1,
                        ModuleId = idx + 1,
                        ModuleCode = r.ModuleCode,
                        ModuleTitle = string.IsNullOrWhiteSpace(r.ModuleTitle) ? r.ModuleCode : r.ModuleTitle,
                        LessonTitle = string.Empty,
                        Summary = string.Empty,
                    });

                foreach (var row in fallback)
                {
                    SubscriptionModules.Add(row);
                }
            }

            if (SelectedSubscriptionModule is null && SubscriptionModules.Count > 0)
            {
                SelectedSubscriptionModule = SubscriptionModules[0];
                OnPropertyChanged(nameof(SelectedSubscriptionModule));
            }

            Quizzes.Clear();
            foreach (var row in quizzes)
            {
                Quizzes.Add(row);
            }
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnSubscribeStarterClicked(object? sender, EventArgs e)
    {
        await SubmitModuleSubscriptionAsync(SelectedSubscriptionModule);
    }

    private async void OnSubscribeProClicked(object? sender, EventArgs e)
    {
        await SubmitModuleSubscriptionAsync(SelectedSubscriptionModule);
    }

    private async void OnSubscribeAllInOneClicked(object? sender, EventArgs e)
    {
        await SubmitModuleSubscriptionAsync(SelectedSubscriptionModule);
    }

    private async void OnSubscribeModuleClicked(object? sender, EventArgs e)
    {
        await SubmitModuleSubscriptionAsync(SelectedSubscriptionModule);
    }

    private async void OnSubscribeLessonModuleClicked(object? sender, EventArgs e)
    {
        if (sender is not Button button || button.CommandParameter is not MobileLearningLesson lesson)
        {
            return;
        }

        await SubmitModuleSubscriptionAsync(lesson);
    }

    private async void OnManageSubscriptionClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new TenantAccountPage());
    }

    private async Task SubmitSubscriptionIntentAsync(string planCode)
    {
        var (ok, message) = await _service.SubmitLearningSubscriptionIntentAsync(planCode, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Learning", message, AlertTone.Error);
            return;
        }

        await ModernAlertService.ShowAsync(this, "Learning", message, AlertTone.Success);
    }

    private async Task SubmitModuleSubscriptionAsync(MobileLearningLesson? module)
    {
        if (module is null)
        {
            await ModernAlertService.ShowAsync(this, "Learning", "Selectionnez un module.", AlertTone.Error);
            return;
        }

        var (ok, message) = await _service.SubmitLearningModuleSubscriptionAsync(module.ModuleId, module.ModuleCode, module.ModuleTitle, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Learning", message, AlertTone.Error);
            return;
        }

        await ModernAlertService.ShowAsync(this, "Learning", message, AlertTone.Success);
    }
}
