using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class TenantAccountPage : ContentPage
{
    public string TenantNameLabel { get; private set; } = "Non connecte";
    public string TenantSlugLabel { get; private set; } = string.Empty;
    public string UserLabel { get; private set; } = string.Empty;

    public TenantAccountPage()
    {
        InitializeComponent();
        RefreshState();
        BindingContext = this;
    }

    private void RefreshState()
    {
        TenantSessionStore.LoadFromDevice();
        var session = TenantSessionStore.Current;
        if (session is null)
        {
            TenantNameLabel = "Non connecte";
            TenantSlugLabel = "";
            UserLabel = "";
            return;
        }

        TenantNameLabel = session.TenantName;
        TenantSlugLabel = $"slug: {session.TenantSlug}";
        UserLabel = $"user: {session.FullName} ({session.UserEmail})";
    }

    private async void OnOpenTenantDashboardClicked(object? sender, EventArgs e)
    {
        TenantSessionStore.LoadFromDevice();
        var session = TenantSessionStore.Current;
        if (session is null)
        {
            await DisplayAlert("Info", "Connectez-vous d'abord.", "OK");
            return;
        }

        await Launcher.Default.OpenAsync($"https://audeladedonnees.fr/tenant/login?tenant={session.TenantSlug}");
    }

    private async void OnLogoutClicked(object? sender, EventArgs e)
    {
        TenantSessionStore.Clear();
        await DisplayAlert("Session", "Deconnecte.", "OK");
        await Navigation.PopToRootAsync();
    }
}
