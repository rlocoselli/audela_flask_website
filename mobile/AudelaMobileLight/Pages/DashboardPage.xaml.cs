using AudelaMobileLight.Services;
using AudelaMobileLight.Models;
using System.Collections.ObjectModel;

namespace AudelaMobileLight.Pages;

public partial class DashboardPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private bool _hasAnimated;
    public ObservableCollection<MobileBiDataSource> BiDataSources { get; } = [];
    public ObservableCollection<MobileBiDashboardSummary> BiDashboards { get; } = [];
    public MobileBiDataSource? SelectedBiDataSource { get; set; }

    public string BiDataSourceCountLabel { get; private set; } = "0";
    public string ActiveSourceLabel { get; private set; } = "-";
    public string DashboardCountLabel { get; private set; } = "0";
    public string QueryRunCountLabel { get; private set; } = "0";
    public bool IsBiEmptyStateVisible { get; private set; }
    public bool IsLoading { get; private set; }

    public DashboardPage()
    {
        InitializeComponent();
        BindingContext = this;
        MobileLocalizer.LanguageChanged += OnLanguageChanged;
        ApplyTranslations();
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        if (!_hasAnimated)
        {
            _hasAnimated = true;
            _ = AnimateEntranceAsync();
        }
        await LoadAsync();
    }

    private async Task LoadAsync()
    {
        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var metrics = await _service.GetDashboardAsync(CancellationToken.None);
            DashboardCountLabel = metrics.DashboardCount.ToString();
            QueryRunCountLabel = metrics.QueryRunCount.ToString();

            var datasources = await _service.GetBiDataSourcesAsync(CancellationToken.None);
            BiDataSources.Clear();
            foreach (var row in datasources)
            {
                BiDataSources.Add(row);
            }
            BiDataSourceCountLabel = BiDataSources.Count.ToString();

            var dashboards = await _service.GetBiDashboardsAsync(CancellationToken.None);
            BiDashboards.Clear();
            foreach (var row in dashboards)
            {
                BiDashboards.Add(row);
            }

            if (SelectedBiDataSource is null && BiDataSources.Count > 0)
            {
                SelectedBiDataSource = BiDataSources[0];
                OnPropertyChanged(nameof(SelectedBiDataSource));
            }
            ActiveSourceLabel = SelectedBiDataSource?.DisplayName ?? "-";
            IsBiEmptyStateVisible = BiDataSources.Count == 0 || BiDashboards.Count == 0;

            OnPropertyChanged(nameof(BiDataSourceCountLabel));
            OnPropertyChanged(nameof(ActiveSourceLabel));
            OnPropertyChanged(nameof(DashboardCountLabel));
            OnPropertyChanged(nameof(QueryRunCountLabel));
            OnPropertyChanged(nameof(IsBiEmptyStateVisible));
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnOpenDashboardClicked(object? sender, EventArgs e)
    {
        if (sender is not Button button || button.CommandParameter is not MobileBiDashboardSummary dashboard)
        {
            return;
        }

        await Navigation.PushAsync(new BiDashboardDetailPage(dashboard));
    }

    private async void OnRefreshDashboardClicked(object? sender, EventArgs e)
    {
        await LoadAsync();
    }

    private async void OnOpenBiSetupClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new ConfigurationPage());
    }

    private string ResolveSelectedSourceCode()
    {
        if (SelectedBiDataSource is not null && !string.IsNullOrWhiteSpace(SelectedBiDataSource.Token))
        {
            return SelectedBiDataSource.Token;
        }

        return string.Empty;
    }

    private async void OnOpenDashboardsHubClicked(object? sender, EventArgs e)
    {
        if (BiDashboards.Count == 0)
        {
            await DisplayAlert("BI", "Aucun dashboard BI disponible.", "OK");
            return;
        }

        await Navigation.PushAsync(new BiDashboardDetailPage(BiDashboards[0]));
    }

    private async void OnOpenQueryStudioClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new BiQueryStudioPage(ResolveSelectedSourceCode()));
    }

    private async void OnOpenChartGalleryClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new BiChartGalleryPage());
    }

    private async void OnOpenAiChatClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new AiChatPage(ResolveSelectedSourceCode()));
    }

    private void OnLanguageChanged(object? sender, EventArgs e)
    {
        ApplyTranslations();
    }

    private void ApplyTranslations()
    {
        // BI home page text remains mostly static for consistency with web labels.
    }

    private async Task AnimateEntranceAsync()
    {
        var blocks = new VisualElement[]
        {
            DashboardHeaderGrid,
            BiMenuCard,
            KpiGrid,
            FinanceGraphCard,
            KanbanGraphCard,
        };

        foreach (var block in blocks)
        {
            block.Opacity = 0;
            block.TranslationY = 16;
        }

        foreach (var block in blocks)
        {
            await Task.WhenAll(
                block.FadeTo(1, 260, Easing.CubicOut),
                block.TranslateTo(0, 0, 260, Easing.CubicOut));
            await Task.Delay(45);
        }
    }
}
