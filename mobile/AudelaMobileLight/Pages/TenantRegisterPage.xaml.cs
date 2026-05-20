using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class TenantRegisterPage : ContentPage
{
    private readonly TenantAuthService _tenantAuthService = new();
    private bool _isSubmitting;

    public bool IsSubmitting
    {
        get => _isSubmitting;
        set
        {
            if (_isSubmitting == value)
            {
                return;
            }

            _isSubmitting = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(IsNotSubmitting));
        }
    }

    public bool IsNotSubmitting => !IsSubmitting;

    public TenantRegisterPage()
    {
        InitializeComponent();
        BindingContext = this;
    }

    private async void OnRegisterClicked(object? sender, EventArgs e)
    {
        if (IsSubmitting)
        {
            return;
        }

        var tenantName = TenantNameEntry.Text?.Trim() ?? string.Empty;
        var email = EmailEntry.Text?.Trim() ?? string.Empty;
        var password = PasswordEntry.Text ?? string.Empty;
        var passwordConfirm = PasswordConfirmEntry.Text ?? string.Empty;

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
        {
            await ModernAlertService.ShowAsync(this, "Erreur", "Email et mot de passe sont requis.", AlertTone.Error);
            return;
        }

        IsSubmitting = true;
        (bool ok, string message) result;
        try
        {
            result = await _tenantAuthService.RegisterAsync(tenantName, email, password, passwordConfirm);
        }
        finally
        {
            IsSubmitting = false;
        }

        var (ok, message) = result;
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Inscription echouee", message, AlertTone.Error);
            return;
        }

        await ModernAlertService.ShowAsync(this, "Compte cree", message, AlertTone.Success);
        await Navigation.PopAsync();
    }
}
