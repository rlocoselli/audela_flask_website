using AudelaMobileLight.Services;
using AudelaMobileLight.Models;
using System.Collections.ObjectModel;

namespace AudelaMobileLight.Pages;

public partial class DashboardPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private bool _hasAnimated;
    public ObservableCollection<MobileAiChatMessage> AiMessages { get; } = [];
    public ObservableCollection<MobileBiDataSource> BiDataSources { get; } = [];
    public ObservableCollection<MobileBiDashboardSummary> BiDashboards { get; } = [];
    public MobileBiDataSource? SelectedBiDataSource { get; set; }

    public string BiDataSourceCountLabel { get; private set; } = "0";
    public string ActiveSourceLabel { get; private set; } = "-";
    public string DashboardCountLabel { get; private set; } = "0";
    public string QueryRunCountLabel { get; private set; } = "0";
    public bool IsLoading { get; private set; }

    public DashboardPage()
    {
        InitializeComponent();
        BindingContext = this;
        MobileLocalizer.LanguageChanged += OnLanguageChanged;
        ApplyTranslations();
        AiMessages.Add(new MobileAiChatMessage { IsUser = false, Text = "Assistant BI pret. Selectionnez une datasource BI et posez votre question." });
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

            OnPropertyChanged(nameof(BiDataSourceCountLabel));
            OnPropertyChanged(nameof(ActiveSourceLabel));
            OnPropertyChanged(nameof(DashboardCountLabel));
            OnPropertyChanged(nameof(QueryRunCountLabel));
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnAskAiClicked(object? sender, EventArgs e)
    {
        var question = AiQuestionEntry.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(question))
        {
            return;
        }

        AiMessages.Insert(0, new MobileAiChatMessage { IsUser = true, Text = question });
        AiQuestionEntry.Text = string.Empty;
        var source = ResolveSelectedSourceCode();
        var (ok, answer) = await _service.AskAiAsync(question, source, MobileLocalizer.CurrentLanguage, CancellationToken.None);
        AiMessages.Insert(0, new MobileAiChatMessage { IsUser = false, Text = ok ? answer : $"AI indisponible: {answer}" });
    }

    private async void OnRefreshDashboardClicked(object? sender, EventArgs e)
    {
        await LoadAsync();
    }

    private string ResolveSelectedSourceCode()
    {
        if (SelectedBiDataSource is not null && !string.IsNullOrWhiteSpace(SelectedBiDataSource.Token))
        {
            return SelectedBiDataSource.Token;
        }

        if (AiSourcePicker.SelectedItem is MobileBiDataSource ds && !string.IsNullOrWhiteSpace(ds.Token))
        {
            return ds.Token;
        }

        return string.Empty;
    }

    private void OnAiSourceChanged(object? sender, EventArgs e)
    {
        if (AiSourcePicker.SelectedItem is MobileBiDataSource ds)
        {
            SelectedBiDataSource = ds;
            ActiveSourceLabel = ds.DisplayName;
            OnPropertyChanged(nameof(SelectedBiDataSource));
            OnPropertyChanged(nameof(ActiveSourceLabel));
        }
    }

    private void OnLanguageChanged(object? sender, EventArgs e)
    {
        ApplyTranslations();
    }

    private void ApplyTranslations()
    {
        AiSourceLabel.Text = MobileLocalizer.T("dashboard.aiSource");
        AskAiButton.Text = MobileLocalizer.T("dashboard.aiAsk");
        AiQuestionEntry.Placeholder = MobileLocalizer.T("dashboard.aiPlaceholder");
    }

    private async Task AnimateEntranceAsync()
    {
        var blocks = new VisualElement[]
        {
            DashboardHeaderGrid,
            KpiGrid,
            FinanceGraphCard,
            KanbanGraphCard,
            AiCard,
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
