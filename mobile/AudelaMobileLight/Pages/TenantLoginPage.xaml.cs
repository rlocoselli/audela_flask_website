using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class TenantLoginPage : ContentPage
{
    private readonly TenantAuthService _tenantAuthService = new();

    public TenantLoginPage()
    {
        InitializeComponent();
    }

    private async void OnLoginClicked(object? sender, EventArgs e)
    {
        var tenantSlug = TenantSlugEntry.Text?.Trim() ?? string.Empty;
        var email = EmailEntry.Text?.Trim() ?? string.Empty;
        var password = PasswordEntry.Text ?? string.Empty;

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
        {
            await DisplayAlert("Erreur", "Email et mot de passe sont requis.", "OK");
            return;
        }

        var (ok, message, session) = await _tenantAuthService.LoginAsync(tenantSlug, email, password);
        if (!ok || session is null)
        {
            await DisplayAlert("Connexion echouee", message, "OK");
            return;
        }

        TenantSessionStore.Save(session);
        await DisplayAlert("Succes", $"Bienvenue {session.FullName}".Trim(), "OK");
        await Navigation.PushAsync(new TenantAccountPage());
    }

    private async void OnRegisterClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new TenantRegisterPage());
    }
}
