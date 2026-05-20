using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class ConfigurationPage : ContentPage
{
    public ConfigurationPage()
    {
        InitializeComponent();
        BindingContext = this;
    }

    private async void OnOpenTenantLoginClicked(object? sender, EventArgs e)
    {
        await Launcher.Default.OpenAsync($"{BackendEndpoints.PrimaryPublicBaseUrl}/tenant/login");
    }

    private async void OnOpenPortalClicked(object? sender, EventArgs e)
    {
        await Launcher.Default.OpenAsync(BackendEndpoints.PrimaryPublicBaseUrl);
    }

    private async void OnOpenTenantAccountClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new TenantAccountPage());
    }
}
