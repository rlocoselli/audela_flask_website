using System.Collections.ObjectModel;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class ConfigurationPage : ContentPage
{
    public ObservableCollection<string> LanguageDisplayValues { get; } = [];
    public string SelectedLanguageDisplay { get; set; } = string.Empty;
    private readonly Dictionary<string, string> _langCodeByDisplay = new(StringComparer.OrdinalIgnoreCase);

    public ConfigurationPage()
    {
        InitializeComponent();
        BindingContext = this;
        MobileLocalizer.LanguageChanged += OnLanguageChanged;
        BuildLanguageOptions();
        ApplyTranslations();
        LanguagePicker.SelectedIndexChanged += OnLanguagePickerChanged;
    }

    private async void OnOpenTenantAccountClicked(object? sender, EventArgs e)
    {
        await Navigation.PushAsync(new TenantAccountPage());
    }

    private void BuildLanguageOptions()
    {
        _langCodeByDisplay.Clear();
        LanguageDisplayValues.Clear();

        foreach (var code in MobileLocalizer.SupportedLanguages)
        {
            var key = $"lang.{code}";
            var label = MobileLocalizer.T(key);
            LanguageDisplayValues.Add(label);
            _langCodeByDisplay[label] = code;
        }

        var currentDisplay = MobileLocalizer.T($"lang.{MobileLocalizer.CurrentLanguage}");
        SelectedLanguageDisplay = currentDisplay;
        OnPropertyChanged(nameof(SelectedLanguageDisplay));
    }

    private void OnLanguagePickerChanged(object? sender, EventArgs e)
    {
        if (LanguagePicker.SelectedItem is not string selectedDisplay)
        {
            return;
        }

        if (_langCodeByDisplay.TryGetValue(selectedDisplay, out var code))
        {
            MobileLocalizer.SetLanguage(code);
        }
    }

    private void OnLanguageChanged(object? sender, EventArgs e)
    {
        BuildLanguageOptions();
        ApplyTranslations();
    }

    private void ApplyTranslations()
    {
        ConfigTitleLabel.Text = MobileLocalizer.T("config.title");
        NativeModeLabel.Text = MobileLocalizer.T("config.native");
        LanguageLabel.Text = MobileLocalizer.T("config.language");
        TenantAccountButton.Text = MobileLocalizer.T("config.account");
        OAuthInfoLabel.Text = MobileLocalizer.T("config.oauth");
    }
}
