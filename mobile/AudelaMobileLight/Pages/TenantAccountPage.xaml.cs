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

    protected override void OnAppearing()
    {
        base.OnAppearing();
        RefreshState();
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
            NotifyLabelsChanged();
            return;
        }

        TenantNameLabel = session.TenantName;
        TenantSlugLabel = $"slug: {session.TenantSlug}";
        UserLabel = $"user: {session.FullName} ({session.UserEmail})";
        NotifyLabelsChanged();
    }

    private void NotifyLabelsChanged()
    {
        OnPropertyChanged(nameof(TenantNameLabel));
        OnPropertyChanged(nameof(TenantSlugLabel));
        OnPropertyChanged(nameof(UserLabel));
    }

    private async void OnOpenWebConfigurationClicked(object? sender, EventArgs e)
    {
        TenantSessionStore.LoadFromDevice();
        var session = TenantSessionStore.Current;
        if (session is null)
        {
            await ModernAlertService.ShowAsync(this, "Info", "Connectez-vous d'abord.");
            return;
        }

        await Launcher.Default.OpenAsync($"{BackendEndpoints.PrimaryPublicBaseUrl}/tenant/login?tenant={session.TenantSlug}");
    }

    private async void OnLogoutClicked(object? sender, EventArgs e)
    {
        TenantSessionStore.Clear();
        await ModernAlertService.ShowAsync(this, "Session", "Deconnecte.", AlertTone.Success);
        await App.NavigateToLoginRootAsync();
    }
}
