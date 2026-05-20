using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class DashboardPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();

    public string FinanceNetAmountLabel { get; private set; } = "0";
    public string LearningProgressLabel { get; private set; } = "0%";
    public string DashboardCountLabel { get; private set; } = "0";
    public string QueryRunCountLabel { get; private set; } = "0";
    public string KanbanBacklogLabel { get; private set; } = "0";
    public string KanbanTodoLabel { get; private set; } = "0";
    public string KanbanDoingLabel { get; private set; } = "0";
    public string KanbanDoneLabel { get; private set; } = "0";
    public bool IsLoading { get; private set; }

    public DashboardPage()
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

            var metrics = await _service.GetDashboardAsync(CancellationToken.None);
            FinanceNetAmountLabel = metrics.FinanceNetAmount.ToString("0.##");
            LearningProgressLabel = $"{metrics.LearningProgressAvg}%";
            DashboardCountLabel = metrics.DashboardCount.ToString();
            QueryRunCountLabel = metrics.QueryRunCount.ToString();
            KanbanBacklogLabel = metrics.KanbanBacklog.ToString();
            KanbanTodoLabel = metrics.KanbanTodo.ToString();
            KanbanDoingLabel = metrics.KanbanDoing.ToString();
            KanbanDoneLabel = metrics.KanbanDone.ToString();

            OnPropertyChanged(nameof(FinanceNetAmountLabel));
            OnPropertyChanged(nameof(LearningProgressLabel));
            OnPropertyChanged(nameof(DashboardCountLabel));
            OnPropertyChanged(nameof(QueryRunCountLabel));
            OnPropertyChanged(nameof(KanbanBacklogLabel));
            OnPropertyChanged(nameof(KanbanTodoLabel));
            OnPropertyChanged(nameof(KanbanDoingLabel));
            OnPropertyChanged(nameof(KanbanDoneLabel));
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }
}
