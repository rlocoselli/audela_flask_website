using Microsoft.Maui.Graphics;

namespace AudelaMobileLight.Pages;

public partial class ModernAlertPage : ContentPage
{
    public string TitleText { get; }
    public string MessageText { get; }
    public Color AccentColor { get; }

    public ModernAlertPage(string title, string message, Color accentColor)
    {
        InitializeComponent();
        TitleText = title;
        MessageText = message;
        AccentColor = accentColor;
        BindingContext = this;
    }

    private async void OnOkClicked(object? sender, EventArgs e)
    {
        await Navigation.PopModalAsync();
    }
}
