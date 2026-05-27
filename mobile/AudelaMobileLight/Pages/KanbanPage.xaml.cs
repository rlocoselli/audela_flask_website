using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class KanbanPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private bool _hasAnimated;
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

        e.Data.Text = item.Id;
        e.Data.Properties["kanbanItemId"] = item.Id;
        e.Data.Properties["kanbanFromColumn"] = _draggedFromColumn;
    }

    private async void OnColumnDrop(object? sender, DropEventArgs e)
    {
        if (sender is not Border border || border.BindingContext is not MobileKanbanColumn targetColumn)
        {
            return;
        }

        if (_draggedItem is null)
        {
            var draggedId = await TryGetDraggedItemIdAsync(e);
            if (!string.IsNullOrWhiteSpace(draggedId))
            {
                _draggedItem = Columns.SelectMany(c => c.Items).FirstOrDefault(i => string.Equals(i.Id, draggedId, StringComparison.Ordinal));
            }
        }

        if (_draggedItem is null)
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

    private async Task<string?> TryGetDraggedItemIdAsync(DropEventArgs e)
    {
        if (e.Data.Properties.TryGetValue("kanbanItemId", out var propValue))
        {
            var asText = propValue?.ToString();
            if (!string.IsNullOrWhiteSpace(asText))
            {
                if (e.Data.Properties.TryGetValue("kanbanFromColumn", out var sourceValue))
                {
                    _draggedFromColumn = sourceValue?.ToString() ?? string.Empty;
                }
                return asText;
            }
        }

        try
        {
            var text = await e.Data.GetTextAsync();
            if (!string.IsNullOrWhiteSpace(text))
            {
                return text;
            }
        }
        catch
        {
            // Ignore payload read errors and fall back to current in-memory drag state.
        }

        return null;
    }

    private async void OnCardDoubleTapped(object? sender, TappedEventArgs e)
    {
        if (sender is not Border border || border.BindingContext is not MobileKanbanItem item)
        {
            return;
        }

        var ownerLabel = MobileLocalizer.T("kanban.details.owner");
        var priorityLabel = MobileLocalizer.T("kanban.details.priority");
        var dueLabel = MobileLocalizer.T("kanban.details.due");
        var title = string.IsNullOrWhiteSpace(item.Title) ? MobileLocalizer.T("kanban.details.title") : item.Title;
        var detail =
            $"ID: {item.Id}\n" +
            $"{ownerLabel}: {item.Owner}\n" +
            $"{priorityLabel}: {item.Priority}\n" +
            $"{dueLabel}: {item.DueDate}\n" +
            $"Column: {item.Column}\n" +
            $"Description: {item.Description}";
        await ModernAlertService.ShowAsync(this, title, detail, AlertTone.Info);
    }

    private void OnCardTapped(object? sender, TappedEventArgs e)
    {
        if (sender is not Border border || border.BindingContext is not MobileKanbanItem item)
        {
            return;
        }
        _ = OpenTaskEditorAsync(item);
    }

    private void OnOpenCreateTaskScreenClicked(object? sender, EventArgs e)
    {
        _ = OpenTaskEditorAsync(null);
    }

    private async Task OpenTaskEditorAsync(MobileKanbanItem? item)
    {
        var editor = new KanbanTaskEditorPage(item);
        editor.Saved += async (_, _) => await LoadAsync();
        await Navigation.PushAsync(editor);
    }

    private async Task AnimateEntranceAsync()
    {
        KanbanHeaderSection.Opacity = 0;
        KanbanHeaderSection.TranslationY = 14;
        KanbanBoardCollection.Opacity = 0;
        KanbanBoardCollection.TranslationY = 20;

        await Task.WhenAll(
            KanbanHeaderSection.FadeTo(1, 260, Easing.CubicOut),
            KanbanHeaderSection.TranslateTo(0, 0, 260, Easing.CubicOut));

        await Task.Delay(40);

        await Task.WhenAll(
            KanbanBoardCollection.FadeTo(1, 280, Easing.CubicOut),
            KanbanBoardCollection.TranslateTo(0, 0, 280, Easing.CubicOut));
    }

}
