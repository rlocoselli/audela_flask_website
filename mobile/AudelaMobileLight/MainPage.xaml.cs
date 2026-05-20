using System.Collections.ObjectModel;
using System.Windows.Input;
using AudelaMobileLight.Models;
using AudelaMobileLight.Pages;
using AudelaMobileLight.Services;

namespace AudelaMobileLight;

public partial class MainPage : ContentPage
{
	private readonly ProductCatalogService _productCatalogService = new();
	private bool _loaded;

	public ObservableCollection<AudelaProduct> Products { get; } = [];
	public bool IsRefreshing { get; set; }
	public string TenantStatusLabel { get; private set; } = "Tenant: non connecte";
	public ICommand RefreshCommand { get; }

	public MainPage()
	{
		InitializeComponent();
		BindingContext = this;
		RefreshCommand = new Command(async () => await LoadProductsAsync());
	}

	protected override async void OnAppearing()
	{
		base.OnAppearing();
		RefreshTenantStatus();
		if (_loaded)
		{
			return;
		}

		_loaded = true;
		await LoadProductsAsync();
	}

	private void RefreshTenantStatus()
	{
		TenantSessionStore.LoadFromDevice();
		TenantStatusLabel = TenantSessionStore.Current is null
			? "Tenant: non connecte"
			: $"Tenant: {TenantSessionStore.Current.TenantName}";
		OnPropertyChanged(nameof(TenantStatusLabel));
	}

	private async void OnTenantButtonClicked(object? sender, EventArgs e)
	{
		TenantSessionStore.LoadFromDevice();
		if (TenantSessionStore.Current is null)
		{
			await Navigation.PushAsync(new TenantLoginPage());
			return;
		}

		await Navigation.PushAsync(new TenantAccountPage());
	}

	private async Task LoadProductsAsync()
	{
		try
		{
			IsRefreshing = true;
			OnPropertyChanged(nameof(IsRefreshing));

			var products = await _productCatalogService.GetProductsAsync(CancellationToken.None);
			Products.Clear();
			foreach (var product in products)
			{
				Products.Add(product);
			}
		}
		catch (Exception ex)
		{
			await ModernAlertService.ShowAsync(this, "Erreur", $"Impossible de charger les produits: {ex.Message}", AlertTone.Error);
		}
		finally
		{
			IsRefreshing = false;
			OnPropertyChanged(nameof(IsRefreshing));
		}
	}

	private async void OnProductSelected(object? sender, SelectionChangedEventArgs e)
	{
		if (e.CurrentSelection.FirstOrDefault() is not AudelaProduct product)
		{
			return;
		}

		ProductsCollection.SelectedItem = null;
		await Navigation.PushAsync(new ProductDetailPage(product));
	}
}
