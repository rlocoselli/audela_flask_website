namespace AudelaMobileLight.Models;

public sealed class TenantSession
{
    public int TenantId { get; set; }
    public string TenantName { get; set; } = string.Empty;
    public string TenantSlug { get; set; } = string.Empty;
    public int UserId { get; set; }
    public string UserEmail { get; set; } = string.Empty;
    public string FullName { get; set; } = string.Empty;
}
