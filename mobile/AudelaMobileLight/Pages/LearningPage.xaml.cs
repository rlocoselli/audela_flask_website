using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class LearningPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public string LearningContentUrl { get; } = $"{BackendEndpoints.PrimaryPublicBaseUrl}/e-learning/";
    public string LearningQuizUrl { get; } = $"{BackendEndpoints.PrimaryPublicBaseUrl}/e-learning/dashboard";
    public string ActiveLearningUrl { get; private set; }
    public ObservableCollection<MobileLearningEnrollment> Enrollments { get; } = [];
    public bool IsLoading { get; private set; }

    public LearningPage()
    {
        InitializeComponent();
        ActiveLearningUrl = LearningContentUrl;
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
            Enrollments.Clear();
            foreach (var row in rows)
            {
                Enrollments.Add(row);
            }
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnOpenCurrentLearningWebClicked(object? sender, EventArgs e)
    {
        await Launcher.Default.OpenAsync(ActiveLearningUrl);
    }

    private void OnShowLearningContentClicked(object? sender, EventArgs e)
    {
        ActiveLearningUrl = LearningContentUrl;
        OnPropertyChanged(nameof(ActiveLearningUrl));
    }

    private void OnShowLearningQuizClicked(object? sender, EventArgs e)
    {
        ActiveLearningUrl = LearningQuizUrl;
        OnPropertyChanged(nameof(ActiveLearningUrl));
    }
}
