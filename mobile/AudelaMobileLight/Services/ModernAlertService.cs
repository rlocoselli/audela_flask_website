using AudelaMobileLight.Pages;
using Microsoft.Maui.Graphics;

namespace AudelaMobileLight.Services;

public enum AlertTone
{
    Info,
    Success,
    Error,
}

public static class ModernAlertService
{
    public static async Task ShowAsync(Page page, string title, string message, AlertTone tone = AlertTone.Info)
    {
        var accent = tone switch
        {
            AlertTone.Success => Color.FromArgb("#4ADE80"),
            AlertTone.Error => Color.FromArgb("#FB7185"),
            _ => Color.FromArgb("#8FD3FF"),
        };

        await page.Navigation.PushModalAsync(new ModernAlertPage(title, message, accent));
    }
}
