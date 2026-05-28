using System.Collections.ObjectModel;
using AudelaMobileLight.Services;
using Microsoft.Maui.Storage;

namespace AudelaMobileLight.Pages;

public partial class ConfigurationPage : ContentPage
{
    private const string ShowAiToolbarPreferenceKey = "ui.show_ai_toolbar";

    private readonly MobileVisualizationService _service = new();
    private readonly Dictionary<string, string> _langCodeByDisplay = new(StringComparer.OrdinalIgnoreCase);

    public ObservableCollection<string> LanguageDisplayValues { get; } = [];
    public ObservableCollection<string> AiProviderValues { get; } = ["openai", "mistral"];

    public string SelectedLanguageDisplay { get; set; } = string.Empty;
    public string SelectedAiProvider { get; set; } = "openai";
    public string AiModelText { get; set; } = string.Empty;
    public string AiRuntimeStatus { get; set; } = string.Empty;

    public ConfigurationPage()
    {
        InitializeComponent();
        BindingContext = this;
        MobileLocalizer.LanguageChanged += OnLanguageChanged;
        BuildLanguageOptions();
        LoadPreferences();
        ApplyTranslations();
        LanguagePicker.SelectedIndexChanged += OnLanguagePickerChanged;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await LoadAiRuntimeAsync();
    }

    private async Task LoadAiRuntimeAsync()
    {
        var (model, provider, label) = await _service.GetAiProfileInfoAsync(CancellationToken.None);
        SelectedAiProvider = string.IsNullOrWhiteSpace(provider) ? "openai" : provider.Trim().ToLowerInvariant();
        AiModelText = model ?? string.Empty;
        AiRuntimeStatus = label;
        OnPropertyChanged(nameof(SelectedAiProvider));
        OnPropertyChanged(nameof(AiModelText));
        OnPropertyChanged(nameof(AiRuntimeStatus));
    }

    private async void OnSaveAiRuntimeClicked(object? sender, EventArgs e)
    {
        SaveAiRuntimeButton.IsEnabled = false;
        try
        {
            var provider = string.IsNullOrWhiteSpace(SelectedAiProvider) ? "openai" : SelectedAiProvider;
            var model = AiModelEntry.Text?.Trim() ?? string.Empty;
            var (ok, message, finalProvider, finalModel, label) = await _service.UpdateAiProfileRuntimeAsync(provider, model, CancellationToken.None);

            if (ok)
            {
                SelectedAiProvider = string.IsNullOrWhiteSpace(finalProvider) ? provider : finalProvider;
                AiModelText = string.IsNullOrWhiteSpace(finalModel) ? model : finalModel;
                AiRuntimeStatus = string.IsNullOrWhiteSpace(label) ? $"{SelectedAiProvider.ToUpperInvariant()} · {AiModelText}" : label;
            }
            else
            {
                AiRuntimeStatus = string.IsNullOrWhiteSpace(message) ? "Unable to update AI runtime." : message;
            }

            OnPropertyChanged(nameof(SelectedAiProvider));
            OnPropertyChanged(nameof(AiModelText));
            OnPropertyChanged(nameof(AiRuntimeStatus));
        }
        finally
        {
            SaveAiRuntimeButton.IsEnabled = true;
        }
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

    private void LoadPreferences()
    {
        AiToolbarSwitch.IsToggled = Preferences.Default.Get(ShowAiToolbarPreferenceKey, true);
    }

    private void OnAiToolbarToggled(object? sender, ToggledEventArgs e)
    {
        Preferences.Default.Set(ShowAiToolbarPreferenceKey, e.Value);
    }

    private void ApplyTranslations()
    {
        ConfigTitleLabel.Text = MobileLocalizer.T("config.title");
        NativeModeLabel.Text = MobileLocalizer.T("config.native");
        LanguageLabel.Text = MobileLocalizer.T("config.language");
        AiToolbarLabel.Text = "Show AI toolbar";
        AiToolbarHintLabel.Text = "Show/hide BI and AI actions on dashboard.";
        AiRuntimeSectionLabel.Text = "AI runtime";
        AiProviderLabel.Text = "Provider";
        AiModelLabel.Text = "Model";
        AiModelEntry.Placeholder = "example: gpt-4o-mini or mistral-small-latest";
        SaveAiRuntimeButton.Text = "Save AI model";
        if (string.IsNullOrWhiteSpace(AiRuntimeStatus))
        {
            AiRuntimeStatus = "loading...";
            OnPropertyChanged(nameof(AiRuntimeStatus));
        }
        TenantAccountButton.Text = MobileLocalizer.T("config.account");
        OAuthInfoLabel.Text = MobileLocalizer.T("config.oauth");
    }
}
