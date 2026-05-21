using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class KanbanPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public ObservableCollection<MobileKanbanColumn> Columns { get; } = [];
    public ObservableCollection<string> PriorityOptions { get; } = ["low", "medium", "high", "critical"];
    public ObservableCollection<string> ColumnOptions { get; } = ["backlog", "todo", "doing", "done"];
    public bool IsLoading { get; private set; }
    public bool IsEditPanelVisible { get; private set; }
    public string SelectedTaskId { get; private set; } = string.Empty;
    public string SelectedTaskIdLabel => string.IsNullOrWhiteSpace(SelectedTaskId) ? string.Empty : $"ID: {SelectedTaskId}";
    public string SelectedTaskTitle { get; set; } = string.Empty;
    public string SelectedTaskDescription { get; set; } = string.Empty;
    public string SelectedTaskOwner { get; set; } = string.Empty;
    public string SelectedTaskPriority { get; set; } = "medium";
    public string SelectedTaskDueDate { get; set; } = string.Empty;
    public string SelectedTaskColumn { get; set; } = "todo";
    private MobileKanbanItem? _draggedItem;
    private string _draggedFromColumn = string.Empty;

    public KanbanPage()
    {
        InitializeComponent();
        BindingContext = this;
        NewPriorityPicker.SelectedItem = "medium";
        NewColumnPicker.SelectedItem = "todo";
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

        SelectedTaskId = item.Id;
        SelectedTaskTitle = item.Title;
        SelectedTaskDescription = item.Description;
        SelectedTaskOwner = item.Owner;
        SelectedTaskPriority = string.IsNullOrWhiteSpace(item.Priority) ? "medium" : item.Priority;
        SelectedTaskDueDate = item.DueDate;
        SelectedTaskColumn = string.IsNullOrWhiteSpace(item.Column) ? "todo" : item.Column;
        IsEditPanelVisible = true;

        EditPriorityPicker.SelectedItem = SelectedTaskPriority;
        EditColumnPicker.SelectedItem = SelectedTaskColumn;

        OnPropertyChanged(nameof(SelectedTaskId));
        OnPropertyChanged(nameof(SelectedTaskIdLabel));
        OnPropertyChanged(nameof(SelectedTaskTitle));
        OnPropertyChanged(nameof(SelectedTaskDescription));
        OnPropertyChanged(nameof(SelectedTaskOwner));
        OnPropertyChanged(nameof(SelectedTaskPriority));
        OnPropertyChanged(nameof(SelectedTaskDueDate));
        OnPropertyChanged(nameof(SelectedTaskColumn));
        OnPropertyChanged(nameof(IsEditPanelVisible));
    }

    private async void OnCreateTaskClicked(object? sender, EventArgs e)
    {
        var title = NewTitleEntry.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(title))
        {
            await ModernAlertService.ShowAsync(this, "Kanban", "Le titre est requis.", AlertTone.Error);
            return;
        }

        var owner = NewOwnerEntry.Text?.Trim() ?? string.Empty;
        var description = NewDescriptionEntry.Text?.Trim() ?? string.Empty;
        var dueDate = NewDueDateEntry.Text?.Trim() ?? string.Empty;
        var priority = (NewPriorityPicker.SelectedItem as string ?? "medium").Trim().ToLowerInvariant();
        var column = (NewColumnPicker.SelectedItem as string ?? "todo").Trim().ToLowerInvariant();

        var (ok, message) = await _service.CreateKanbanTaskAsync(title, description, owner, priority, dueDate, column, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Kanban", message, AlertTone.Error);
            return;
        }

        NewTitleEntry.Text = string.Empty;
        NewOwnerEntry.Text = string.Empty;
        NewDescriptionEntry.Text = string.Empty;
        NewDueDateEntry.Text = string.Empty;
        NewPriorityPicker.SelectedItem = "medium";
        NewColumnPicker.SelectedItem = "todo";

        await ModernAlertService.ShowAsync(this, "Kanban", message, AlertTone.Success);
        await LoadAsync();
    }

    private async void OnSaveTaskChangesClicked(object? sender, EventArgs e)
    {
        if (string.IsNullOrWhiteSpace(SelectedTaskId))
        {
            return;
        }

        var title = EditTitleEntry.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(title))
        {
            await ModernAlertService.ShowAsync(this, "Kanban", "Le titre est requis.", AlertTone.Error);
            return;
        }

        var owner = EditOwnerEntry.Text?.Trim() ?? string.Empty;
        var description = EditDescriptionEntry.Text?.Trim() ?? string.Empty;
        var dueDate = EditDueDateEntry.Text?.Trim() ?? string.Empty;
        var priority = (EditPriorityPicker.SelectedItem as string ?? "medium").Trim().ToLowerInvariant();
        var column = (EditColumnPicker.SelectedItem as string ?? "todo").Trim().ToLowerInvariant();

        var (ok, message) = await _service.UpdateKanbanTaskAsync(SelectedTaskId, title, description, owner, priority, dueDate, column, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Kanban", message, AlertTone.Error);
            return;
        }

        await ModernAlertService.ShowAsync(this, "Kanban", message, AlertTone.Success);
        await LoadAsync();
    }

}
