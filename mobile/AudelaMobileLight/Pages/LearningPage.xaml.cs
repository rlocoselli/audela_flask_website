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
        await SubmitSubscriptionIntentAsync("e_learning_starter");
    }

    private async void OnSubscribeProClicked(object? sender, EventArgs e)
    {
        await SubmitSubscriptionIntentAsync("e_learning_pro");
    }

    private async void OnSubscribeAllInOneClicked(object? sender, EventArgs e)
    {
        await SubmitSubscriptionIntentAsync("all_in_one_pro");
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
}
