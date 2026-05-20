using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class KanbanPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public string ProjectKanbanUrl { get; } = $"{BackendEndpoints.PrimaryPublicBaseUrl}/project/";
    public ObservableCollection<MobileKanbanColumn> Columns { get; } = [];
    public bool IsLoading { get; private set; }

    public KanbanPage()
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

            var cols = await _service.GetKanbanAsync(CancellationToken.None);
            Columns.Clear();
            foreach (var col in cols)
            {
                Columns.Add(col);
            }
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnOpenProjectWebClicked(object? sender, EventArgs e)
    {
        await Launcher.Default.OpenAsync(ProjectKanbanUrl);
    }
}
