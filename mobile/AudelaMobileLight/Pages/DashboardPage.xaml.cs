using AudelaMobileLight.Services;
using System.Collections.ObjectModel;

namespace AudelaMobileLight.Pages;

public partial class DashboardPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public ObservableCollection<string> AiMessages { get; } = [];

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
        AiMessages.Add("Assistant AI pret. Pose ta question BI/Finance/Projet/Learning.");
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
        var (ok, answer) = await _service.AskAiAsync(question, CancellationToken.None);
        AiMessages.Insert(0, ok ? $"AI: {answer}" : $"AI indisponible: {answer}");
    }
}
