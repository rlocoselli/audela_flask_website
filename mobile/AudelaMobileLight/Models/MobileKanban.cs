namespace AudelaMobileLight.Models;

public sealed class MobileKanbanColumn
{
    public string Key { get; set; } = string.Empty;
    public int Count { get; set; }
    public List<MobileKanbanItem> Items { get; set; } = [];
}

public sealed class MobileKanbanItem
{
    public string Id { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Owner { get; set; } = string.Empty;
    public string Priority { get; set; } = string.Empty;
    public string DueDate { get; set; } = string.Empty;
}
