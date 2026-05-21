using AudelaMobileLight.Services;
using System.Collections.ObjectModel;

namespace AudelaMobileLight.Pages;

public partial class DashboardPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private bool _hasAnimated;
    public ObservableCollection<string> AiMessages { get; } = [];
    public ObservableCollection<string> AiSourceLabels { get; } = [];
    public string SelectedAiSourceLabel { get; set; } = string.Empty;
    private readonly Dictionary<string, string> _sourceByLabel = new(StringComparer.OrdinalIgnoreCase);

    public string FinanceNetAmountLabel { get; private set; } = "0";
    public string DailyInLabel { get; private set; } = "0";
    public string DailyOutLabel { get; private set; } = "0";
    public double DailyInRatio { get; private set; }
    public double DailyOutRatio { get; private set; }
    public string LearningProgressLabel { get; private set; } = "0%";
    public string DashboardCountLabel { get; private set; } = "0";
    public string QueryRunCountLabel { get; private set; } = "0";
    public string KanbanBacklogLabel { get; private set; } = "0";
    public string KanbanTodoLabel { get; private set; } = "0";
    public string KanbanDoingLabel { get; private set; } = "0";
    public string KanbanDoneLabel { get; private set; } = "0";
    public double KanbanBacklogRatio { get; private set; }
    public double KanbanTodoRatio { get; private set; }
    public double KanbanDoingRatio { get; private set; }
    public double KanbanDoneRatio { get; private set; }
    public bool IsLoading { get; private set; }

    public DashboardPage()
    {
        InitializeComponent();
        BindingContext = this;
        MobileLocalizer.LanguageChanged += OnLanguageChanged;
        BuildAiSources();
        ApplyTranslations();
        AiMessages.Add("Assistant AI pret. Pose ta question BI/Finance/Projet/Learning.");
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
            var financeSummary = await _service.GetFinanceSummaryAsync(CancellationToken.None);
            FinanceNetAmountLabel = metrics.FinanceNetAmount.ToString("0.##");
            DailyInLabel = financeSummary.DailyIn.ToString("0.##");
            DailyOutLabel = financeSummary.DailyOut.ToString("0.##");
            LearningProgressLabel = $"{metrics.LearningProgressAvg}%";
            DashboardCountLabel = metrics.DashboardCount.ToString();
            QueryRunCountLabel = metrics.QueryRunCount.ToString();
            KanbanBacklogLabel = metrics.KanbanBacklog.ToString();
            KanbanTodoLabel = metrics.KanbanTodo.ToString();
            KanbanDoingLabel = metrics.KanbanDoing.ToString();
            KanbanDoneLabel = metrics.KanbanDone.ToString();

            var dailyMax = Math.Max(1.0, Math.Max(financeSummary.DailyIn, financeSummary.DailyOut));
            DailyInRatio = Math.Clamp(financeSummary.DailyIn / dailyMax, 0.0, 1.0);
            DailyOutRatio = Math.Clamp(financeSummary.DailyOut / dailyMax, 0.0, 1.0);

            var kanbanTotal = Math.Max(1, metrics.KanbanBacklog + metrics.KanbanTodo + metrics.KanbanDoing + metrics.KanbanDone);
            KanbanBacklogRatio = Math.Clamp((double)metrics.KanbanBacklog / kanbanTotal, 0.0, 1.0);
            KanbanTodoRatio = Math.Clamp((double)metrics.KanbanTodo / kanbanTotal, 0.0, 1.0);
            KanbanDoingRatio = Math.Clamp((double)metrics.KanbanDoing / kanbanTotal, 0.0, 1.0);
            KanbanDoneRatio = Math.Clamp((double)metrics.KanbanDone / kanbanTotal, 0.0, 1.0);

            OnPropertyChanged(nameof(FinanceNetAmountLabel));
            OnPropertyChanged(nameof(DailyInLabel));
            OnPropertyChanged(nameof(DailyOutLabel));
            OnPropertyChanged(nameof(DailyInRatio));
            OnPropertyChanged(nameof(DailyOutRatio));
            OnPropertyChanged(nameof(LearningProgressLabel));
            OnPropertyChanged(nameof(DashboardCountLabel));
            OnPropertyChanged(nameof(QueryRunCountLabel));
            OnPropertyChanged(nameof(KanbanBacklogLabel));
            OnPropertyChanged(nameof(KanbanTodoLabel));
            OnPropertyChanged(nameof(KanbanDoingLabel));
            OnPropertyChanged(nameof(KanbanDoneLabel));
            OnPropertyChanged(nameof(KanbanBacklogRatio));
            OnPropertyChanged(nameof(KanbanTodoRatio));
            OnPropertyChanged(nameof(KanbanDoingRatio));
            OnPropertyChanged(nameof(KanbanDoneRatio));
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

        AiMessages.Insert(0, $"Vous: {question}");
        AiQuestionEntry.Text = string.Empty;
        var source = ResolveSelectedSourceCode();
        var (ok, answer) = await _service.AskAiAsync(question, source, MobileLocalizer.CurrentLanguage, CancellationToken.None);
        AiMessages.Insert(0, ok ? $"AI: {answer}" : $"AI indisponible: {answer}");
    }

    private async void OnRefreshDashboardClicked(object? sender, EventArgs e)
    {
        await LoadAsync();
    }

    private void BuildAiSources()
    {
        _sourceByLabel.Clear();
        AiSourceLabels.Clear();

        AddSource("dashboard.source.auto", "auto");
        AddSource("dashboard.source.finance", "finance");
        AddSource("dashboard.source.kanban", "kanban");
        AddSource("dashboard.source.learning", "learning");
        AddSource("dashboard.source.dashboard", "dashboard");

        if (AiSourceLabels.Count > 0)
        {
            SelectedAiSourceLabel = AiSourceLabels[0];
            OnPropertyChanged(nameof(SelectedAiSourceLabel));
        }
    }

    private void AddSource(string key, string value)
    {
        var label = MobileLocalizer.T(key);
        AiSourceLabels.Add(label);
        _sourceByLabel[label] = value;
    }

    private string ResolveSelectedSourceCode()
    {
        var selected = SelectedAiSourceLabel;
        if (string.IsNullOrWhiteSpace(selected) && AiSourcePicker.SelectedItem is string selectedFromPicker)
        {
            selected = selectedFromPicker;
        }

        if (!string.IsNullOrWhiteSpace(selected) && _sourceByLabel.TryGetValue(selected, out var source))
        {
            return source;
        }

        return "auto";
    }

    private void OnLanguageChanged(object? sender, EventArgs e)
    {
        BuildAiSources();
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
