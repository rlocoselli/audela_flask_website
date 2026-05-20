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
}
