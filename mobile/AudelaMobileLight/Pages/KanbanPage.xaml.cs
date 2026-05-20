using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class KanbanPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public ObservableCollection<MobileKanbanColumn> Columns { get; } = [];
    public bool IsLoading { get; private set; }
    private MobileKanbanItem? _draggedItem;
    private string _draggedFromColumn = string.Empty;

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

    private void OnCardDragStarting(object? sender, DragStartingEventArgs e)
    {
        if (sender is not Border border || border.BindingContext is not MobileKanbanItem item)
        {
            return;
        }

        _draggedItem = item;
        var parentColumn = Columns.FirstOrDefault(c => c.Items.Any(i => i.Id == item.Id));
        _draggedFromColumn = parentColumn?.Key ?? string.Empty;
    }

    private async void OnColumnDrop(object? sender, DropEventArgs e)
    {
        if (_draggedItem is null || sender is not Border border || border.BindingContext is not MobileKanbanColumn targetColumn)
        {
            return;
        }

        var targetKey = (targetColumn.Key ?? string.Empty).Trim().ToLowerInvariant();
        if (string.IsNullOrWhiteSpace(targetKey) || targetKey == (_draggedFromColumn ?? string.Empty).Trim().ToLowerInvariant())
        {
            _draggedItem = null;
            _draggedFromColumn = string.Empty;
            return;
        }

        var (ok, message) = await _service.MoveKanbanCardAsync(_draggedItem.Id, targetKey, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Kanban", message, AlertTone.Error);
        }

        _draggedItem = null;
        _draggedFromColumn = string.Empty;
        await LoadAsync();
    }

}
