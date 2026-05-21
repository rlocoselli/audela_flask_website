using System.Collections.ObjectModel;
using System.Globalization;
using System.Text.RegularExpressions;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;
using Microsoft.Extensions.DependencyInjection;

namespace AudelaMobileLight.Pages;

public partial class FinanceEntriesPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    private readonly IVoiceRecognitionService _voiceRecognitionService;
    private bool _hasAnimated;
    public ObservableCollection<MobileFinanceEntry> Entries { get; } = [];
    public bool IsLoading { get; private set; }
    public bool ShowDashboardSection { get; private set; } = true;
    public bool ShowTransactionsSection { get; private set; }
    public bool ShowQuickEntrySection { get; private set; }
    public string DailyInLabel { get; private set; } = "0";
    public string DailyOutLabel { get; private set; } = "0";
    public string DailyNetLabel { get; private set; } = "0";
    public string MonthlyInLabel { get; private set; } = "0";
    public string MonthlyOutLabel { get; private set; } = "0";
    public string MonthlyNetLabel { get; private set; } = "0";

    public FinanceEntriesPage()
    {
        InitializeComponent();
        BindingContext = this;
        _voiceRecognitionService = Application.Current?.Handler?.MauiContext?.Services.GetService<IVoiceRecognitionService>() ?? new NoopVoiceRecognitionService();
        MobileLocalizer.LanguageChanged += OnLanguageChanged;
        ApplyTranslations();
        SetSection("dashboard");
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        if (!_hasAnimated)
        {
            _hasAnimated = true;
            _ = AnimateEntranceAsync();
        }
        await LoadAsync();
    }

    private async Task LoadAsync()
    {
        try
        {
            IsLoading = true;
            OnPropertyChanged(nameof(IsLoading));

            var rows = await _service.GetFinanceEntriesAsync(CancellationToken.None);
            var summary = await _service.GetFinanceSummaryAsync(CancellationToken.None);

            DailyInLabel = summary.DailyIn.ToString("0.##");
            DailyOutLabel = summary.DailyOut.ToString("0.##");
            DailyNetLabel = summary.DailyNet.ToString("0.##");
            MonthlyInLabel = summary.MonthlyIn.ToString("0.##");
            MonthlyOutLabel = summary.MonthlyOut.ToString("0.##");
            MonthlyNetLabel = summary.MonthlyNet.ToString("0.##");

            OnPropertyChanged(nameof(DailyInLabel));
            OnPropertyChanged(nameof(DailyOutLabel));
            OnPropertyChanged(nameof(DailyNetLabel));
            OnPropertyChanged(nameof(MonthlyInLabel));
            OnPropertyChanged(nameof(MonthlyOutLabel));
            OnPropertyChanged(nameof(MonthlyNetLabel));

            Entries.Clear();
            foreach (var row in rows)
            {
                Entries.Add(row);
            }
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private async void OnAddQuickEntryClicked(object? sender, EventArgs e)
    {
        var description = DescriptionEntry.Text?.Trim() ?? string.Empty;
        var category = CategoryEntry.Text?.Trim() ?? string.Empty;
        var amountRaw = AmountEntry.Text?.Trim() ?? string.Empty;

        if (string.IsNullOrWhiteSpace(description) || string.IsNullOrWhiteSpace(amountRaw))
        {
            await ModernAlertService.ShowAsync(this, MobileLocalizer.T("finance.error"), MobileLocalizer.T("finance.required"), AlertTone.Error);
            return;
        }

        if (!double.TryParse(amountRaw.Replace(',', '.'), NumberStyles.Any, CultureInfo.InvariantCulture, out var amount))
        {
            await ModernAlertService.ShowAsync(this, MobileLocalizer.T("finance.error"), MobileLocalizer.T("finance.invalidAmount"), AlertTone.Error);
            return;
        }

        var (ok, message) = await _service.AddFinanceEntryAsync(description, category, amount, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, MobileLocalizer.T("finance.inputFail"), message, AlertTone.Error);
            return;
        }

        DescriptionEntry.Text = string.Empty;
        CategoryEntry.Text = string.Empty;
        AmountEntry.Text = string.Empty;
        await ModernAlertService.ShowAsync(this, MobileLocalizer.T("finance.success"), message, AlertTone.Success);
        await LoadAsync();
    }

    private void OnDashboardMenuClicked(object? sender, EventArgs e) => _ = SetSectionAsync("dashboard");

    private void OnTransactionsMenuClicked(object? sender, EventArgs e) => _ = SetSectionAsync("transactions");

    private void OnQuickEntryMenuClicked(object? sender, EventArgs e) => _ = SetSectionAsync("quick");

    private async void OnFloatingQuickEntryClicked(object? sender, EventArgs e)
    {
        await SetSectionAsync("quick");
        await RunVoiceRecognitionAsync();
    }

    private async void OnVoiceQuickEntryClicked(object? sender, EventArgs e)
    {
        await RunVoiceRecognitionAsync();
    }

    private async Task RunVoiceRecognitionAsync()
    {
        var (ok, text, message) = await _voiceRecognitionService.RecognizeAsync(CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, MobileLocalizer.T("finance.error"), message, AlertTone.Error);
            return;
        }

        ApplyTranscript(text);
    }

    private void ApplyTranscript(string transcript)
    {
        var normalized = (transcript ?? string.Empty).Trim();
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return;
        }

        var amountMatch = Regex.Match(normalized, @"[-+]?\d+(?:[\.,]\d+)?");
        if (amountMatch.Success && string.IsNullOrWhiteSpace(AmountEntry.Text))
        {
            AmountEntry.Text = amountMatch.Value.Replace(',', '.');
        }

        if (string.IsNullOrWhiteSpace(DescriptionEntry.Text))
        {
            var description = amountMatch.Success
                ? normalized.Replace(amountMatch.Value, string.Empty).Trim(' ', '-', ':', ';')
                : normalized;
            DescriptionEntry.Text = string.IsNullOrWhiteSpace(description) ? normalized : description;
        }
    }

    private void SetSection(string section)
    {
        ShowDashboardSection = section == "dashboard";
        ShowTransactionsSection = section == "transactions";
        ShowQuickEntrySection = section == "quick";
        OnPropertyChanged(nameof(ShowDashboardSection));
        OnPropertyChanged(nameof(ShowTransactionsSection));
        OnPropertyChanged(nameof(ShowQuickEntrySection));

        DashboardMenuButton.BackgroundColor = ShowDashboardSection ? Color.FromArgb("#0A84FF") : Color.FromArgb("#DDEAF9");
        DashboardMenuButton.TextColor = ShowDashboardSection ? Colors.White : Color.FromArgb("#12304B");

        TransactionsMenuButton.BackgroundColor = ShowTransactionsSection ? Color.FromArgb("#0A84FF") : Color.FromArgb("#DDEAF9");
        TransactionsMenuButton.TextColor = ShowTransactionsSection ? Colors.White : Color.FromArgb("#12304B");

        QuickEntryMenuButton.BackgroundColor = ShowQuickEntrySection ? Color.FromArgb("#0A84FF") : Color.FromArgb("#DDEAF9");
        QuickEntryMenuButton.TextColor = ShowQuickEntrySection ? Colors.White : Color.FromArgb("#12304B");
    }

    private async Task SetSectionAsync(string section)
    {
        var current = GetActiveSection();
        if (!string.IsNullOrWhiteSpace(current) && current != section)
        {
            var currentElement = ResolveSectionElement(current);
            if (currentElement is not null)
            {
                await Task.WhenAll(
                    currentElement.FadeTo(0, 130, Easing.CubicIn),
                    currentElement.TranslateTo(0, 10, 130, Easing.CubicIn));
                currentElement.TranslationY = 0;
            }
        }

        SetSection(section);

        var nextElement = ResolveSectionElement(section);
        if (nextElement is not null)
        {
            nextElement.Opacity = 0;
            nextElement.TranslationY = 12;
            await Task.WhenAll(
                nextElement.FadeTo(1, 170, Easing.CubicOut),
                nextElement.TranslateTo(0, 0, 170, Easing.CubicOut));
        }
    }

    private string GetActiveSection()
    {
        if (ShowDashboardSection)
        {
            return "dashboard";
        }

        if (ShowTransactionsSection)
        {
            return "transactions";
        }

        if (ShowQuickEntrySection)
        {
            return "quick";
        }

        return string.Empty;
    }

    private VisualElement? ResolveSectionElement(string section)
    {
        return section switch
        {
            "dashboard" => FinanceDashboardSection,
            "transactions" => FinanceTransactionsSection,
            "quick" => FinanceQuickEntrySection,
            _ => null,
        };
    }

    private void OnLanguageChanged(object? sender, EventArgs e)
    {
        ApplyTranslations();
    }

    private void ApplyTranslations()
    {
        PageTitleLabel.Text = MobileLocalizer.T("finance.title");
        PageSubtitleLabel.Text = MobileLocalizer.T("finance.subtitle");
        DashboardMenuButton.Text = MobileLocalizer.T("finance.menu.dashboard");
        TransactionsMenuButton.Text = MobileLocalizer.T("finance.menu.transactions");
        QuickEntryMenuButton.Text = MobileLocalizer.T("finance.menu.quick");
        VoiceQuickEntryButton.Text = MobileLocalizer.T("finance.voiceBtn");
        FloatingQuickEntryButton.Text = MobileLocalizer.T("finance.voiceFab");
    }

    private async Task AnimateEntranceAsync()
    {
        var blocks = new VisualElement[]
        {
            FinanceMenuGrid,
            FinanceDashboardSection,
            FinanceTransactionsSection,
            FinanceQuickEntrySection,
        };

        foreach (var block in blocks)
        {
            block.Opacity = 0;
            block.TranslationY = 14;
        }

        FloatingQuickEntryButton.Opacity = 0;
        FloatingQuickEntryButton.Scale = 0.85;

        foreach (var block in blocks)
        {
            await Task.WhenAll(
                block.FadeTo(1, 240, Easing.CubicOut),
                block.TranslateTo(0, 0, 240, Easing.CubicOut));
            await Task.Delay(35);
        }

        await Task.WhenAll(
            FloatingQuickEntryButton.FadeTo(1, 220, Easing.CubicOut),
            FloatingQuickEntryButton.ScaleTo(1, 220, Easing.SpringOut));
    }

}
