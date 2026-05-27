using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class TenantLoginPage : ContentPage
{
    private readonly TenantAuthService _tenantAuthService = new();
    public bool IsSubmitting { get; private set; }
    public bool IsNotSubmitting => !IsSubmitting;

    public TenantLoginPage()
    {
        InitializeComponent();
        BindingContext = this;
    }

    private async void OnLoginClicked(object? sender, EventArgs e)
    {
        if (IsSubmitting)
        {
            return;
        }

        var tenantSlug = TenantSlugEntry.Text?.Trim() ?? string.Empty;
        var email = EmailEntry.Text?.Trim() ?? string.Empty;
        var password = PasswordEntry.Text ?? string.Empty;

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
        {
            await ModernAlertService.ShowAsync(this, "Erreur", "Email et mot de passe sont requis.", AlertTone.Error);
            return;
        }

        IsSubmitting = true;
        OnPropertyChanged(nameof(IsSubmitting));
        OnPropertyChanged(nameof(IsNotSubmitting));

        try
        {
            var (ok, message, session) = await _tenantAuthService.LoginAsync(tenantSlug, email, password);
            if (!ok || session is null)
            {
                await ModernAlertService.ShowAsync(this, "Connexion echouee", message, AlertTone.Error);
                return;
            }

            TenantSessionStore.Save(session);
            await ModernAlertService.ShowAsync(this, "Succes", $"Bienvenue {session.FullName}".Trim(), AlertTone.Success);
            await App.NavigateToAuthenticatedRootAsync();
        }
        finally
        {
            IsSubmitting = false;
            OnPropertyChanged(nameof(IsSubmitting));
            OnPropertyChanged(nameof(IsNotSubmitting));
        }
    }

    private async void OnRegisterClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new TenantRegisterPage());
    }

    private async void OnGoogleLoginClicked(object? sender, EventArgs e)
    {
        var tenantSlug = TenantSlugEntry.Text?.Trim().ToLowerInvariant() ?? string.Empty;
        var baseUrl = BackendEndpoints.PrimaryPublicBaseUrl;
        var mobileReturn = Uri.EscapeDataString("audelamobilelight://oauth-callback");
        var googleLoginUrl = $"{baseUrl}/app/login/google/start?app=tenant&mode=login&mobile_return={mobileReturn}";

        if (!string.IsNullOrWhiteSpace(tenantSlug))
        {
            googleLoginUrl += $"&tenant_slug={Uri.EscapeDataString(tenantSlug)}";
        }

        await Launcher.Default.OpenAsync(googleLoginUrl);
    }
}
