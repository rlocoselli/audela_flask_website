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
    private int _currentPage = 1;
    private const int PageSize = 10;
    private int _filterYear = DateTime.Now.Year;
    private int _filterMonth = DateTime.Now.Month;

    public ObservableCollection<MobileFinanceEntry> Entries { get; } = [];
    public ObservableCollection<MobileFinanceEntry> PagedEntries { get; } = [];
    public ObservableCollection<MobileFinanceAccount> Accounts { get; } = [];
    public ObservableCollection<MobileFinanceCategoryTotal> ExpenseCategoryTotals { get; } = [];
    public ObservableCollection<MobileFinanceCategoryTotal> RevenueCategoryTotals { get; } = [];
    public ObservableCollection<string> QuickCategories { get; } =
    [
        "Sales",
        "Subscriptions",
        "Consulting",
        "Operations",
        "Marketing",
        "Payroll",
        "Taxes",
        "Rent",
        "Logistics",
        "Other",
    ];
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
    public string SelectedCategory { get; set; } = "Other";
    public MobileFinanceAccount? SelectedAccount { get; set; }
    public Command<MobileFinanceEntry> ShowEntryDetailCommand { get; }

    public FinanceEntriesPage()
    {
        InitializeComponent();
        BindingContext = this;

        ShowEntryDetailCommand = new Command<MobileFinanceEntry>(async entry =>
        {
            if (entry is not null)
            {
                await Navigation.PushAsync(new FinanceEntryDetailPage(entry));
            }
        });

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
            var accounts = await _service.GetFinanceAccountsAsync(CancellationToken.None);
            var categoryReport = await _service.GetFinanceCategoryReportAsync(CancellationToken.None);

            DailyInLabel = summary.DailyIn.ToString("0.00");
            DailyOutLabel = summary.DailyOut.ToString("0.00");
            DailyNetLabel = summary.DailyNet.ToString("0.00");
            MonthlyInLabel = summary.MonthlyIn.ToString("0.00");
            MonthlyOutLabel = summary.MonthlyOut.ToString("0.00");
            MonthlyNetLabel = summary.MonthlyNet.ToString("0.00");

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

            Accounts.Clear();
            foreach (var row in accounts)
            {
                Accounts.Add(row);
            }

            if (SelectedAccount is null && Accounts.Count > 0)
            {
                SelectedAccount = Accounts[0];
                OnPropertyChanged(nameof(SelectedAccount));
            }

            ExpenseCategoryTotals.Clear();
            foreach (var row in categoryReport.Expenses)
            {
                ExpenseCategoryTotals.Add(row);
            }

            RevenueCategoryTotals.Clear();
            foreach (var row in categoryReport.Revenues)
            {
                RevenueCategoryTotals.Add(row);
            }

            ApplyFilterAndPaging();
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsLoading));
        }
    }

    private void ApplyFilterAndPaging()
    {
        var monthPrefix = new DateTime(_filterYear, _filterMonth, 1).ToString("yyyy-MM");
        var filtered = Entries.Where(e => e.Date.StartsWith(monthPrefix)).ToList();
        var totalPages = Math.Max(1, (int)Math.Ceiling(filtered.Count / (double)PageSize));
        if (_currentPage > totalPages)
        {
            _currentPage = totalPages;
        }

        var page = filtered.Skip((_currentPage - 1) * PageSize).Take(PageSize).ToList();
        PagedEntries.Clear();
        foreach (var entry in page)
        {
            PagedEntries.Add(entry);
        }

        MainThread.BeginInvokeOnMainThread(() =>
        {
            if (DateFilterLabel is not null)
            {
                DateFilterLabel.Text = new DateTime(_filterYear, _filterMonth, 1).ToString("MM/yyyy", CultureInfo.CurrentCulture);
            }

            if (PageLabel is not null)
            {
                PageLabel.Text = $"Page {_currentPage} / {totalPages}";
            }

            if (TransactionCountLabel is not null)
            {
                TransactionCountLabel.Text = $"{filtered.Count} transaction{(filtered.Count != 1 ? "s" : string.Empty)}";
            }
        });
    }

    private void OnPrevMonthClicked(object? sender, EventArgs e)
    {
        _filterMonth--;
        if (_filterMonth == 0) { _filterMonth = 12; _filterYear--; }
        _currentPage = 1;
        ApplyFilterAndPaging();
    }

    private void OnNextMonthClicked(object? sender, EventArgs e)
    {
        _filterMonth++;
        if (_filterMonth == 13) { _filterMonth = 1; _filterYear++; }
        _currentPage = 1;
        ApplyFilterAndPaging();
    }

    private void OnPrevPageClicked(object? sender, EventArgs e)
    {
        if (_currentPage > 1)
        {
            _currentPage--;
            ApplyFilterAndPaging();
        }
    }

    private void OnNextPageClicked(object? sender, EventArgs e)
    {
        var monthPrefix = new DateTime(_filterYear, _filterMonth, 1).ToString("yyyy-MM");
        var filtered = Entries.Where(e => e.Date.StartsWith(monthPrefix)).ToList();
        var totalPages = Math.Max(1, (int)Math.Ceiling(filtered.Count / (double)PageSize));
        if (_currentPage < totalPages)
        {
            _currentPage++;
            ApplyFilterAndPaging();
        }
    }

    private async void OnAddQuickEntryClicked(object? sender, EventArgs e)
    {
        var description = DescriptionEntry.Text?.Trim() ?? string.Empty;
        var category = SelectedCategory?.Trim() ?? string.Empty;
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

        AddQuickEntryButton.IsEnabled = false;
        try
        {
            var accountId = SelectedAccount?.Id;
            var (ok, message) = await _service.AddFinanceEntryAsync(description, category, amount, accountId, CancellationToken.None);
            if (!ok)
            {
                await ModernAlertService.ShowAsync(this, MobileLocalizer.T("finance.inputFail"), message, AlertTone.Error);
                return;
            }

            DescriptionEntry.Text = string.Empty;
            SelectedCategory = "Other";
            OnPropertyChanged(nameof(SelectedCategory));
            AmountEntry.Text = string.Empty;
            await ModernAlertService.ShowAsync(this, MobileLocalizer.T("finance.success"), message, AlertTone.Success);
            await LoadAsync();
        }
        finally
        {
            AddQuickEntryButton.IsEnabled = true;
        }
    }

    private void OnDashboardMenuClicked(object? sender, EventArgs e) => _ = SetSectionAsync("dashboard");

    private void OnTransactionsMenuClicked(object? sender, EventArgs e)
    {
        _ = SetSectionAsync("transactions");
        ApplyFilterAndPaging();
    }

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

        DashboardMenuButton.BackgroundColor = ShowDashboardSection ? Color.FromArgb("#136A9B") : Color.FromArgb("#DDEAF9");
        DashboardMenuButton.TextColor = ShowDashboardSection ? Colors.White : Color.FromArgb("#12304B");

        TransactionsMenuButton.BackgroundColor = ShowTransactionsSection ? Color.FromArgb("#136A9B") : Color.FromArgb("#DDEAF9");
        TransactionsMenuButton.TextColor = ShowTransactionsSection ? Colors.White : Color.FromArgb("#12304B");

        QuickEntryMenuButton.BackgroundColor = ShowQuickEntrySection ? Color.FromArgb("#136A9B") : Color.FromArgb("#DDEAF9");
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
            block.TranslationY = 18;
        }

        foreach (var block in blocks)
        {
            await Task.WhenAll(
                block.FadeTo(1, 210, Easing.CubicOut),
                block.TranslateTo(0, 0, 210, Easing.CubicOut));
            await Task.Delay(40);
        }
    }
}
