using System.Collections.ObjectModel;
using AudelaMobileLight.Models;
using AudelaMobileLight.Services;

namespace AudelaMobileLight.Pages;

public partial class FinanceEntriesPage : ContentPage
{
    private readonly MobileVisualizationService _service = new();
    public ObservableCollection<MobileFinanceEntry> Entries { get; } = [];
    public bool IsLoading { get; private set; }

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
}
