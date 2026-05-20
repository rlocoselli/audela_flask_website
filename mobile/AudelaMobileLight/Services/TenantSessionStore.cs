using AudelaMobileLight.Models;

namespace AudelaMobileLight.Services;

public static class TenantSessionStore
{
    private const string TenantIdKey = "tenant.id";
    private const string TenantNameKey = "tenant.name";
    private const string TenantSlugKey = "tenant.slug";
    private const string UserIdKey = "tenant.user.id";
    private const string UserEmailKey = "tenant.user.email";
    private const string UserFullNameKey = "tenant.user.fullname";

    public static TenantSession? Current { get; private set; }

    public static bool IsLoggedIn => Current is not null;

    public static void LoadFromDevice()
    {
        var tenantId = Preferences.Default.Get(TenantIdKey, 0);
        var userId = Preferences.Default.Get(UserIdKey, 0);
        if (tenantId <= 0 || userId <= 0)
        {
            Current = null;
            return;
        }

        Current = new TenantSession
        {
            TenantId = tenantId,
            TenantName = Preferences.Default.Get(TenantNameKey, string.Empty),
            TenantSlug = Preferences.Default.Get(TenantSlugKey, string.Empty),
            UserId = userId,
            UserEmail = Preferences.Default.Get(UserEmailKey, string.Empty),
            FullName = Preferences.Default.Get(UserFullNameKey, string.Empty),
        };
    }

    public static void Save(TenantSession session)
    {
        Current = session;
        Preferences.Default.Set(TenantIdKey, session.TenantId);
        Preferences.Default.Set(TenantNameKey, session.TenantName);
        Preferences.Default.Set(TenantSlugKey, session.TenantSlug);
        Preferences.Default.Set(UserIdKey, session.UserId);
        Preferences.Default.Set(UserEmailKey, session.UserEmail);
        Preferences.Default.Set(UserFullNameKey, session.FullName);
    }

    public static void Clear()
    {
        Current = null;
        Preferences.Default.Remove(TenantIdKey);
        Preferences.Default.Remove(TenantNameKey);
        Preferences.Default.Remove(TenantSlugKey);
        Preferences.Default.Remove(UserIdKey);
        Preferences.Default.Remove(UserEmailKey);
        Preferences.Default.Remove(UserFullNameKey);
    }
}
