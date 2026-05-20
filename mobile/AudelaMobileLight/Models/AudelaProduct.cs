namespace AudelaMobileLight.Models;

public sealed class AudelaProduct
{
    public string Id { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Subtitle { get; set; } = string.Empty;
    public string Summary { get; set; } = string.Empty;
    public string Audience { get; set; } = string.Empty;
    public string Tag { get; set; } = string.Empty;
    public List<string> FeatureHighlights { get; set; } = [];
    public List<string> OutcomeHighlights { get; set; } = [];
}
