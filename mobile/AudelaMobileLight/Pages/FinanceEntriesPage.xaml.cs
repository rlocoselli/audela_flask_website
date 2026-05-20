using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class FinanceEntriesPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public ObservableCollection<MobileFinanceEntry> Entries { get; } = [];
    public bool IsLoading { get; private set; }
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
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
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
            await ModernAlertService.ShowAsync(this, "Erreur", "Description et montant sont requis.", AlertTone.Error);
            return;
        }

        if (!double.TryParse(amountRaw.Replace(',', '.'), System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out var amount))
        {
            await ModernAlertService.ShowAsync(this, "Erreur", "Montant invalide.", AlertTone.Error);
            return;
        }

        var (ok, message) = await _service.AddFinanceEntryAsync(description, category, amount, CancellationToken.None);
        if (!ok)
        {
            await ModernAlertService.ShowAsync(this, "Saisie impossible", message, AlertTone.Error);
            return;
        }

        DescriptionEntry.Text = string.Empty;
        CategoryEntry.Text = string.Empty;
        AmountEntry.Text = string.Empty;
        await ModernAlertService.ShowAsync(this, "Succes", message, AlertTone.Success);
        await LoadAsync();
    }

}
