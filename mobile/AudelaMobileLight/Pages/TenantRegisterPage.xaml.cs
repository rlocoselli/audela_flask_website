using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class TenantRegisterPage : ContentPage
{
    private readonly TenantAuthService _tenantAuthService = new();

    public TenantRegisterPage()
    {
        InitializeComponent();
    }

    private async void OnRegisterClicked(object? sender, EventArgs e)
    {
        var tenantName = TenantNameEntry.Text?.Trim() ?? string.Empty;
        var email = EmailEntry.Text?.Trim() ?? string.Empty;
        var password = PasswordEntry.Text ?? string.Empty;
        var passwordConfirm = PasswordConfirmEntry.Text ?? string.Empty;

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
        {
            await DisplayAlert("Erreur", "Email et mot de passe sont requis.", "OK");
            return;
        }

        var (ok, message) = await _tenantAuthService.RegisterAsync(tenantName, email, password, passwordConfirm);
        if (!ok)
        {
            await DisplayAlert("Inscription echouee", message, "OK");
            return;
        }

        await DisplayAlert("Compte cree", message, "OK");
        await Navigation.PopAsync();
    }
}
