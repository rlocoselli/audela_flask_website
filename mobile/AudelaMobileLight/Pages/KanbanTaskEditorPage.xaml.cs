using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class KanbanTaskEditorPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();

    public event EventHandler? Saved;

    public ObservableCollection<string> PriorityOptions { get; } = ["low", "medium", "high", "critical"];
    public ObservableCollection<string> ColumnOptions { get; } = ["backlog", "todo", "doing", "done"];

    public string TaskId { get; private set; } = string.Empty;
    public bool IsCreateMode => string.IsNullOrWhiteSpace(TaskId);
    public string HeaderTitle => IsCreateMode ? "Nouvelle tache" : "Modifier la tache";
    public string TaskTitle { get; set; } = string.Empty;
    public string TaskDescription { get; set; } = string.Empty;
    public string TaskOwner { get; set; } = string.Empty;
    public string TaskPriority { get; set; } = "medium";
    public string TaskDueDate { get; set; } = string.Empty;
    public string TaskColumn { get; set; } = "todo";

    public KanbanTaskEditorPage(MobileKanbanItem? item = null)
    {
        InitializeComponent();

        if (item is not null)
        {
            TaskId = item.Id;
            TaskTitle = item.Title;
            TaskDescription = item.Description;
            TaskOwner = item.Owner;
            TaskPriority = string.IsNullOrWhiteSpace(item.Priority) ? "medium" : item.Priority;
            TaskDueDate = item.DueDate;
            TaskColumn = string.IsNullOrWhiteSpace(item.Column) ? "todo" : item.Column;
        }

        BindingContext = this;
        PriorityPicker.SelectedItem = TaskPriority;
        ColumnPicker.SelectedItem = TaskColumn;
    }

    private async void OnSaveClicked(object? sender, EventArgs e)
    {
        var title = TitleEntry.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(title))
        {
            await ModernAlertService.ShowAsync(this, "Kanban", "Le titre est requis.", AlertTone.Error);
            return;
        }

        var owner = OwnerEntry.Text?.Trim() ?? string.Empty;
        var description = DescriptionEditor.Text?.Trim() ?? string.Empty;
        var dueDate = DueDateEntry.Text?.Trim() ?? string.Empty;
        var priority = (PriorityPicker.SelectedItem as string ?? "medium").Trim().ToLowerInvariant();
        var column = (ColumnPicker.SelectedItem as string ?? "todo").Trim().ToLowerInvariant();

        (bool ok, string message) result = IsCreateMode
            ? await _service.CreateKanbanTaskAsync(title, description, owner, priority, dueDate, column, CancellationToken.None)
            : await _service.UpdateKanbanTaskAsync(TaskId, title, description, owner, priority, dueDate, column, CancellationToken.None);

        if (!result.ok)
        {
            await ModernAlertService.ShowAsync(this, "Kanban", result.message, AlertTone.Error);
            return;
        }

        Saved?.Invoke(this, EventArgs.Empty);
        await Navigation.PopAsync();
    }
}
