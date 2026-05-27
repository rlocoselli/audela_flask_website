using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class AiChatPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly string _defaultSourceToken;

    public ObservableCollection<MobileAiChatMessage> AiMessages { get; } = [];
    public ObservableCollection<MobileBiDataSource> BiDataSources { get; } = [];
    public MobileBiDataSource? SelectedBiDataSource { get; set; }

    public AiChatPage(string defaultSourceToken = "")
    {
        _defaultSourceToken = defaultSourceToken;
        InitializeComponent();
        BindingContext = this;

        AiMessages.Add(new MobileAiChatMessage
        {
            IsUser = false,
            Text = "Assistant BI pret. Selectionnez une datasource BI et posez votre question.",
        });

        ApplyTranslations();
        MobileLocalizer.LanguageChanged += OnLanguageChanged;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await EnsureDataSourcesLoadedAsync();
    }

    private async Task EnsureDataSourcesLoadedAsync()
    {
        if (BiDataSources.Count > 0)
        {
            return;
        }

        var rows = await _service.GetBiDataSourcesAsync(CancellationToken.None);
        BiDataSources.Clear();
        foreach (var row in rows)
        {
            BiDataSources.Add(row);
        }

        var selected = BiDataSources.FirstOrDefault(x => string.Equals(x.Token, _defaultSourceToken, StringComparison.OrdinalIgnoreCase));
        SelectedBiDataSource = selected ?? BiDataSources.FirstOrDefault();
        OnPropertyChanged(nameof(SelectedBiDataSource));
    }

    private async void OnAskAiClicked(object? sender, EventArgs e)
    {
        var question = AiQuestionEntry.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(question))
        {
            return;
        }

        AiMessages.Insert(0, new MobileAiChatMessage { IsUser = true, Text = question });
        AiQuestionEntry.Text = string.Empty;

        var source = SelectedBiDataSource?.Token ?? string.Empty;
        var (ok, answer) = await _service.AskAiAsync(question, source, MobileLocalizer.CurrentLanguage, CancellationToken.None);
        AiMessages.Insert(0, new MobileAiChatMessage
        {
            IsUser = false,
            Text = ok ? answer : $"AI indisponible: {answer}",
        });
    }

    private void OnAiQuestionCompleted(object? sender, EventArgs e)
    {
        OnAskAiClicked(sender, e);
    }

    private void OnAiSourceChanged(object? sender, EventArgs e)
    {
        if (AiSourcePicker.SelectedItem is MobileBiDataSource ds)
        {
            SelectedBiDataSource = ds;
            OnPropertyChanged(nameof(SelectedBiDataSource));
        }
    }

    private void OnLanguageChanged(object? sender, EventArgs e)
    {
        ApplyTranslations();
    }

    private void ApplyTranslations()
    {
        AiSourceLabel.Text = MobileLocalizer.T("dashboard.aiSource");
        AskAiButton.Text = MobileLocalizer.T("dashboard.aiAsk");
        AiQuestionEntry.Placeholder = MobileLocalizer.T("dashboard.aiPlaceholder");
    }
}
